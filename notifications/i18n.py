"""Hindi display of known system templates; stored history and email remain unchanged."""
from .catalog import render, _SafeDict

HINDI = {
    'document_integrity_failed': ('संग्रहीत दस्तावेज़ की अखंडता जाँच विफल: {reference}', 'FDR {reference} की संग्रहीत फ़ाइल {document} अब अपलोड के समय दर्ज चेकसम से मेल नहीं खाती, इसलिए डाउनलोड रोके गए हैं। दस्तावेज़ को अविश्वसनीय मानें और संस्थान से इसे फिर अपलोड करने को कहें।'),
    'instrument_submitted': ('समीक्षा के लिए नई जमा: {reference}', 'संस्थान ने FDR {reference} समीक्षा के लिए जमा की है। समीक्षा के लिए पोर्टल खोलें।'),
    'instrument_accepted': ('FDR {reference} निगरानी के लिए स्वीकृत', 'FDR {reference} निगरानी के लिए स्वीकार हुई है। यह बैंक का सत्यापन नहीं है।'),
    'instrument_changes_requested': ('FDR {reference} में सुधार माँगे गए', 'अधिकारी ने FDR {reference} में सुधार माँगे हैं। टिप्पणियाँ देखने के लिए पोर्टल खोलें।'),
    'verification_discrepancy': ('FDR {reference} का विवरणी से मिलान नहीं हुआ', 'विवरणी की पंक्ति FDR {reference} से मेल नहीं खाती। अधिकारी की समीक्षा आवश्यक है।'),
    'verification_confirmed': ('FDR {reference} का विवरणी से मिलान पुष्ट', 'बैंक विवरणी की पंक्ति FDR {reference} से मिली (डेमो में स्रोत अनुकरणित है)।'),
    'release_requested': ('FDR {reference} की मुक्ति का अनुरोध', 'FDR {reference} की मुक्ति का अनुरोध जमा हुआ है। अनापत्ति कार्य खुले हैं।'),
    'clearance_assigned': ('FDR {reference} के लिए {unit} अनापत्ति आवश्यक', 'FDR {reference} के लिए {unit} अनापत्ति कार्य आपकी इकाई की प्रतीक्षा में है।'),
    'penalty_proposed': ('FDR {reference} पर दंड प्रस्तावित', 'FDR {reference} का दंड आकलन निर्णय की प्रतीक्षा में है।'),
    'release_decided': ('FDR {reference} की मुक्ति पर निर्णय', 'FDR {reference} के मुक्ति अनुरोध पर निर्णय दर्ज हुआ है।'),
    'noc_issued': ('FDR {reference} का पत्र जारी', 'FDR {reference} का अनापत्ति प्रमाणपत्र या स्वीकृति आदेश पोर्टल में तैयार है।'),
    'maturity_reminder': ('FDR {reference} {days} दिनों में परिपक्व होगी', 'FDR {reference} की परिपक्वता तिथि {maturity_date} है ({days} दिनों में)। नवीनीकरण की योजना बनाएँ।'),
    'renewal_overdue': ('नवीनीकरण की समय सीमा बीती: FDR {reference}', 'FDR {reference} {maturity_date} को परिपक्व हुई; कोई उत्तराधिकारी जमा स्वीकृत नहीं है।'),
    'penalty_review_due': ('दंड समीक्षा देय: FDR {reference}', 'FDR {reference} की परिपक्वता को {days} दिन बीत गए। दंड की समीक्षा करें (APH 7.7)।'),
    'proof_due_reminder': ('जमा प्रमाण देय: 15 में से दिन {day}', '{institution} का जमा प्रमाण देय है। सूचना के बाद 15 में से दिन {day}; दंड श्रेणी: {band}।'),
    'sla_submission_pending': ('FDR {reference}: समीक्षा के लिए {days} दिन से लंबित', 'FDR {reference} की समीक्षा {days} दिन से लंबित है (सीमा {limit})।'),
    'sla_correction_pending': ('FDR {reference}: सुधार {days} दिन से लंबित', 'FDR {reference} में माँगे गए सुधार {days} दिन बाद भी लंबित हैं।'),
    'sla_clearance_pending': ('FDR {reference}: {unit} अनापत्ति {days} दिन से लंबित', 'FDR {reference} की {unit} अनापत्ति {days} दिन से खुली है (सीमा {limit})।'),
}


def display_translations(notification):
    if not isinstance(notification.context, dict):
        return {}
    template = HINDI.get(notification.template_id)
    if not template:
        return {}
    subject, body, _, _ = render(notification.template_id, notification.context)
    # A changed/custom historical message must not be silently reinterpreted.
    if (subject, body) != (notification.subject, notification.body):
        return {}
    values = _SafeDict(notification.context or {})
    return {'hi': {'subject': template[0].format_map(values), 'body': template[1].format_map(values)}}
