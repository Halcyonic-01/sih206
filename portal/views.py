from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from . import releases, services
from .deadlines import (CATEGORIES, business_today, classify_maturity, dashboard_counts,
                        filter_instruments, parse_as_of, reminder_days)
from .forms import (InstrumentForm, ObservationForm, RenewalForm, ResolutionForm, ReviewForm, SubmitForm,
                    ReleaseRequestForm, ReleaseDecisionForm, ReleaseCompletionForm)
from .models import Document, Instrument, ReleaseRequest
from .permissions import institution_for, require_authority, require_officer, role, scoped_instruments
from .validation import CHECKS_VERSION, run_checks
from .exports import register_csv
from access.logging import log_access
from access.models import AccessLog


def reporting_context(request):
    explicit_date = request.GET.get('as_of', '')
    if explicit_date and not settings.DEBUG:
        raise ValueError('Browser date overrides are available only in local DEBUG demo mode.')
    return {'as_of': parse_as_of(explicit_date), 'demo_date': bool(explicit_date),
            'allow_demo_date': settings.DEBUG, 'business_timezone': settings.TIME_ZONE,
            'reminder_days': reminder_days()}


@login_required
@never_cache
def dashboard(request):
    records = scoped_instruments(request.user).select_related('institution')
    try:
        context = reporting_context(request)
    except ValueError as exc:
        return render(request, 'portal/report_error.html', {'error': str(exc)}, status=400)
    counts = dashboard_counts(records, context['as_of'])
    cards = []
    for category, label in CATEGORIES.items():
        query = {'category': category}
        if context['demo_date']:
            query['as_of'] = context['as_of'].isoformat()
        cards.append({'category': category, 'label': label, 'count': counts[category],
                      'url': reverse('instrument_list') + '?' + urlencode(query)})
    return render(request, 'portal/dashboard.html', {
        **context, 'cards': cards, 'counts': counts, 'role': role(request.user),
    })


def filtered_register(request):
    current_role = role(request.user)
    records = scoped_instruments(request.user).select_related('institution')
    category = request.GET.get('category', 'pending' if current_role == 'officer' else 'all')
    context = reporting_context(request)
    return filter_instruments(records, category, context['as_of']), context, category, current_role


@login_required
@never_cache
def instrument_export(request):
    try:
        records, context, _, _ = filtered_register(request)
    except ValueError as exc:
        return render(request, 'portal/report_error.html', {'error': str(exc)}, status=400)
    log_access(request, AccessLog.EXPORT, object_type='instrument_register',
               detail=f'rows={records.count()} query={request.GET.urlencode()[:200]}')
    return register_csv(records, context['as_of'])


@login_required
@never_cache
def instrument_list(request):
    try:
        records, context, category, current_role = filtered_register(request)
    except ValueError as exc:
        return render(request, 'portal/report_error.html', {'error': str(exc)}, status=400)
    rows = [{'instrument': record, 'maturity': classify_maturity(record.maturity_date, context['as_of']),
             'is_monitored': record.is_current} for record in records]
    return render(request, 'portal/instrument_list.html', {
        **context, 'instruments': records, 'instrument_rows': rows, 'record_count': len(rows),
        'role': current_role, 'category': category, 'category_label': CATEGORIES[category],
        'categories': CATEGORIES,
        'export_query': urlencode({'category': category, **({'as_of': context['as_of'].isoformat()}
                                                            if context['demo_date'] else {})}),
    })


@login_required
def instrument_create(request):
    institution = institution_for(request.user)
    form = InstrumentForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        instrument = services.save_draft(request.user, form.cleaned_data)
        messages.success(request, 'Draft saved. Review the details, then submit for officer review.')
        return redirect('instrument_detail', pk=instrument.pk)
    return render(request, 'portal/instrument_form.html', {'form': form, 'institution': institution})


@login_required
def instrument_edit(request, pk):
    institution = institution_for(request.user)
    instrument = get_object_or_404(scoped_instruments(request.user), pk=pk)
    if instrument.status not in (Instrument.Status.DRAFT, Instrument.Status.CHANGES_REQUESTED):
        return render(request, 'portal/conflict.html', {'error': 'This record is locked for editing.'}, status=409)
    form = InstrumentForm(request.POST or None, request.FILES or None, instance=instrument)
    status = 200
    if request.method == 'POST' and form.is_valid():
        try:
            services.save_draft(request.user, form.cleaned_data, pk)
        except services.WorkflowError as exc:
            form.add_error(None, str(exc))
            status = 409
        else:
            messages.success(request, 'Changes saved. Earlier documents and history have been preserved.')
            return redirect('instrument_detail', pk=pk)
    return render(request, 'portal/instrument_form.html',
                  {'form': form, 'instrument': instrument, 'institution': institution}, status=status)


@login_required
@never_cache
def instrument_renew(request, pk):
    institution = institution_for(request.user)
    predecessor = get_object_or_404(scoped_instruments(request.user), pk=pk)
    if not predecessor.is_current:
        return render(request, 'portal/conflict.html',
                      {'error': 'Only an accepted current instrument can start a renewal.'}, status=409)
    if predecessor.has_active_release:
        return render(request, 'portal/conflict.html',
                      {'error': 'A pending or authorized release blocks this renewal.'}, status=409)
    if Instrument.objects.filter(predecessor=predecessor).exists():
        return render(request, 'portal/conflict.html',
                      {'error': 'A successor proposal already exists. Open it from the predecessor detail page.'}, status=409)
    form = RenewalForm(request.POST or None, request.FILES or None, initial={
        'bank': predecessor.bank, 'amount': predecessor.amount,
        'predecessor_version': predecessor.version,
    })
    status = 200
    if request.method == 'POST' and form.is_valid():
        try:
            successor = services.save_draft(request.user, form.cleaned_data, predecessor_id=pk)
        except services.WorkflowError as exc:
            form.add_error(None, str(exc))
            status = 409
        else:
            messages.success(request, 'Linked renewal draft saved. The predecessor remains current until officer acceptance.')
            return redirect('instrument_detail', pk=successor.pk)
    return render(request, 'portal/instrument_form.html', {
        'form': form, 'institution': institution, 'predecessor': predecessor,
    }, status=status)


def detail_context(user, instrument, review_form=None, action_error=None,
                   observation_form=None, resolution_form=None, resolution_observation_id=None,
                   release_request_form=None, release_decision_form=None, release_completion_form=None,
                   release_id=None):
    current_role = role(user)
    editable = (current_role == 'institution' and instrument.status in
                (Instrument.Status.DRAFT, Instrument.Status.CHANGES_REQUESTED))
    reviewable = current_role == 'officer' and instrument.status == Instrument.Status.SUBMITTED
    observations = instrument.observations.select_related('document', 'reviewer', 'resolved_by')
    observation_rows = [{
        'observation': observation,
        'resolution_form': resolution_form if observation.pk == resolution_observation_id else
            ResolutionForm(initial={'version': instrument.version}, auto_id=f'resolution_{observation.pk}_%s'),
    } for observation in observations]
    today = business_today()
    visible = scoped_instruments(user)
    predecessor = visible.filter(pk=instrument.predecessor_id).first() if instrument.predecessor_id else None
    successor = visible.filter(predecessor_id=instrument.pk).first()
    release_rows = []
    for release in instrument.release_requests.select_related('requested_by', 'decided_by', 'completed_by', 'completion_evidence'):
        independent_authority = (current_role == 'authority' and release.requested_by_id != user.pk
                                 and instrument.is_current)
        release_rows.append({
            'release': release,
            'can_decide': independent_authority and release.status == ReleaseRequest.Status.PENDING,
            'can_complete': independent_authority and release.status == ReleaseRequest.Status.APPROVED,
            'decision_form': release_decision_form if release.pk == release_id and release_decision_form is not None
                else ReleaseDecisionForm(initial={'version': instrument.version}, auto_id=f'release_decision_{release.pk}_%s'),
            'completion_form': release_completion_form if release.pk == release_id and release_completion_form is not None
                else ReleaseCompletionForm(initial={'version': instrument.version}, auto_id=f'release_completion_{release.pk}_%s'),
        })
    active_release = instrument.has_active_release
    return {
        'instrument': instrument, 'role': current_role, 'editable': editable,
        'documents': instrument.documents.select_related('uploaded_by'),
        'events': instrument.audit_events.select_related('actor'),
        'submit_form': SubmitForm(initial={'version': instrument.version}),
        'review_form': review_form if review_form is not None else ReviewForm(initial={'version': instrument.version}),
        'reviewable': reviewable,
        'action_error': action_error,
        'findings': run_checks(instrument), 'checks_version': CHECKS_VERSION,
        'observation_rows': observation_rows,
        'can_observe': reviewable and user.pk != instrument.created_by_id,
        'observation_form': observation_form if observation_form is not None else
            ObservationForm(instrument=instrument, initial={'version': instrument.version}, auto_id='observation_%s'),
        'maturity': classify_maturity(instrument.maturity_date, today),
        'maturity_as_of': today, 'business_timezone': settings.TIME_ZONE,
        'maturity_monitored': instrument.is_current,
        'predecessor': predecessor, 'successor': successor,
        'can_renew': current_role == 'institution' and instrument.is_current and successor is None and not active_release,
        'can_request_release': current_role == 'institution' and instrument.is_current and successor is None and not active_release,
        'release_rows': release_rows,
        'active_release': active_release,
        'release_request_form': release_request_form if release_request_form is not None else
            ReleaseRequestForm(initial={'version': instrument.version}, auto_id='release_request_%s'),
    }


@login_required
@never_cache
def instrument_detail(request, pk):
    instrument = get_object_or_404(scoped_instruments(request.user).select_related('institution'), pk=pk)
    return render(request, 'portal/instrument_detail.html', detail_context(request.user, instrument))


@login_required
@require_POST
def instrument_submit(request, pk):
    institution_for(request.user)
    instrument = get_object_or_404(scoped_instruments(request.user), pk=pk)
    form = SubmitForm(request.POST)
    if not form.is_valid():
        error, status = 'Invalid submission. Reload the record and try again.', 400
    else:
        try:
            services.submit(request.user, pk, form.cleaned_data['version'])
        except services.WorkflowError as exc:
            error, status = str(exc), 409
        else:
            messages.success(request, 'Submitted for officer review.')
            return redirect('instrument_detail', pk=pk)
    instrument.refresh_from_db()
    return render(request, 'portal/instrument_detail.html',
                  detail_context(request.user, instrument, action_error=error), status=status)


@login_required
@require_POST
def instrument_review(request, pk):
    require_officer(request.user)
    instrument = get_object_or_404(scoped_instruments(request.user), pk=pk)
    form = ReviewForm(request.POST)
    error, status = None, 400
    if form.is_valid():
        try:
            services.review(request.user, pk, **{
                'expected_version': form.cleaned_data['version'],
                'decision': form.cleaned_data['decision'], 'reason': form.cleaned_data['reason'],
            })
        except services.WorkflowError as exc:
            error, status = str(exc), 409
        else:
            messages.success(request, 'Review decision recorded.')
            return redirect('instrument_detail', pk=pk)
    instrument.refresh_from_db()
    return render(request, 'portal/instrument_detail.html',
                  detail_context(request.user, instrument, form, error), status=status)


@login_required
@require_POST
def observation_add(request, pk):
    require_officer(request.user)
    instrument = get_object_or_404(scoped_instruments(request.user), pk=pk)
    form = ObservationForm(request.POST, instrument=instrument, auto_id='observation_%s')
    error, status = None, 400
    if form.is_valid():
        try:
            services.add_observation(request.user, pk, expected_version=form.cleaned_data['version'],
                                     **{key: form.cleaned_data[key] for key in
                                        ('document', 'page_number', 'severity', 'comment')})
        except services.WorkflowError as exc:
            error, status = str(exc), 409
        else:
            messages.success(request, 'Manual observation recorded with its document reference.')
            return redirect('instrument_detail', pk=pk)
    instrument.refresh_from_db()
    return render(request, 'portal/instrument_detail.html',
                  detail_context(request.user, instrument, action_error=error, observation_form=form), status=status)


@login_required
@require_POST
def observation_resolve(request, pk, observation_pk):
    require_officer(request.user)
    instrument = get_object_or_404(scoped_instruments(request.user), pk=pk)
    get_object_or_404(instrument.observations, pk=observation_pk)
    form = ResolutionForm(request.POST, auto_id=f'resolution_{observation_pk}_%s')
    error, status = None, 400
    if form.is_valid():
        try:
            services.resolve_observation(request.user, pk, observation_pk,
                                         form.cleaned_data['version'], form.cleaned_data['resolution'])
        except services.WorkflowError as exc:
            error, status = str(exc), 409
        else:
            messages.success(request, 'Observation resolved. The original finding remains in history.')
            return redirect('instrument_detail', pk=pk)
    instrument.refresh_from_db()
    return render(request, 'portal/instrument_detail.html', detail_context(
        request.user, instrument, action_error=error, resolution_form=form,
        resolution_observation_id=observation_pk), status=status)


@login_required
@never_cache
def document_download(request, pk):
    document = get_object_or_404(Document.objects.filter(
        instrument__in=scoped_instruments(request.user)), pk=pk)
    log_access(request, AccessLog.DOCUMENT_DOWNLOAD, document, detail=f'instrument={document.instrument_id}')
    try:
        response = FileResponse(document.file.open('rb'), as_attachment=True,
                                filename=document.original_name, content_type='application/pdf')
    except FileNotFoundError:
        raise Http404('Document is unavailable. Contact the portal operator.')
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
@never_cache
def release_queue(request):
    records = scoped_instruments(request.user)
    choices = {'ALL': 'All requests', **dict(ReleaseRequest.Status.choices)}
    selected = request.GET.get('status', 'ALL' if role(request.user) == 'institution' else 'PENDING')
    if selected not in choices:
        return render(request, 'portal/report_error.html', {'error': 'Unknown release status.'}, status=400)
    requests = ReleaseRequest.objects.filter(instrument__in=records)
    if selected != 'ALL':
        requests = requests.filter(status=selected)
    return render(request, 'portal/release_queue.html', {
        'releases': requests.select_related('instrument__institution', 'requested_by'),
        'statuses': choices, 'selected_status': selected, 'role': role(request.user),
    })


@login_required
@require_POST
@never_cache
def release_request(request, pk):
    institution_for(request.user)
    instrument = get_object_or_404(scoped_instruments(request.user), pk=pk)
    form = ReleaseRequestForm(request.POST, auto_id='release_request_%s')
    error, status = None, 400
    if form.is_valid():
        try:
            releases.request_release(request.user, pk, form.cleaned_data['version'], form.cleaned_data['reason'])
        except services.WorkflowError as exc:
            error, status = str(exc), 409
        else:
            messages.success(request, 'Release request submitted for an independent authority decision.')
            return redirect('instrument_detail', pk=pk)
    instrument.refresh_from_db()
    return render(request, 'portal/instrument_detail.html', detail_context(
        request.user, instrument, action_error=error, release_request_form=form), status=status)


@login_required
@require_POST
@never_cache
def release_decision(request, pk, release_pk):
    require_authority(request.user)
    instrument = get_object_or_404(scoped_instruments(request.user), pk=pk)
    get_object_or_404(instrument.release_requests, pk=release_pk)
    form = ReleaseDecisionForm(request.POST, auto_id=f'release_decision_{release_pk}_%s')
    error, status = None, 400
    if form.is_valid():
        try:
            releases.decide_release(request.user, pk, release_pk, form.cleaned_data['version'],
                                    form.cleaned_data['decision'], form.cleaned_data['reason'])
        except services.WorkflowError as exc:
            error, status = str(exc), 409
        else:
            messages.success(request, 'Authority decision recorded. Authorization alone does not complete release.')
            return redirect('instrument_detail', pk=pk)
    instrument.refresh_from_db()
    return render(request, 'portal/instrument_detail.html', detail_context(
        request.user, instrument, action_error=error, release_decision_form=form, release_id=release_pk), status=status)


@login_required
@require_POST
@never_cache
def release_completion(request, pk, release_pk):
    require_authority(request.user)
    instrument = get_object_or_404(scoped_instruments(request.user), pk=pk)
    get_object_or_404(instrument.release_requests, pk=release_pk)
    form = ReleaseCompletionForm(request.POST, request.FILES, auto_id=f'release_completion_{release_pk}_%s')
    error, status = None, 400
    if form.is_valid():
        try:
            releases.complete_release(request.user, pk, release_pk, form.cleaned_data['version'],
                                      form.cleaned_data['notes'], form.cleaned_data['document'])
        except services.WorkflowError as exc:
            error, status = str(exc), 409
        else:
            messages.success(request, 'Release completion recorded with its evidence PDF. No payment was executed by this portal.')
            return redirect('instrument_detail', pk=pk)
    instrument.refresh_from_db()
    return render(request, 'portal/instrument_detail.html', detail_context(
        request.user, instrument, action_error=error, release_completion_form=form, release_id=release_pk), status=status)
