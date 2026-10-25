import { BankOutlined } from '@ant-design/icons';
import { lazy } from 'react';
import type { AppRoute } from '@/routes/types';

const List = lazy(() => import('./InstitutionPages').then(module => ({ default: module.InstitutionsPage })));
const Detail = lazy(() => import('./InstitutionPages').then(module => ({ default: module.InstitutionPage })));
const Calculator = lazy(() => import('./InstitutionPages').then(module => ({ default: module.InstitutionCalculatorPage })));
const Reports = lazy(() => import('./ReportPages').then(module => ({ default: module.ReportsPage })));
const Kpis = lazy(() => import('./ReportPages').then(module => ({ default: module.KpisPage })));
const Import = lazy(() => import('./ReportPages').then(module => ({ default: module.InstitutionImportPage })));
const ReleaseRequest = lazy(() => import('./ReleasePages').then(module => ({ default: module.ReleaseRequestPage })));
const ReleaseCases = lazy(() => import('./ReleasePages').then(module => ({ default: module.ReleaseCasesPage })));
const ReleaseCase = lazy(() => import('./ReleasePages').then(module => ({ default: module.ReleaseCasePage })));
const ClearanceQueue = lazy(() => import('./ReleasePages').then(module => ({ default: module.ClearanceQueuePage })));
const PublicVerification = lazy(() => import('./ReleasePages').then(module => ({ default: module.PublicVerificationPage })));

export const routes: AppRoute[] = [
  { path: '/institutions', element: <List />, roles: ['institution', 'officer', 'authority'],
    menu: { label: 'Institutions', icon: <BankOutlined />, order: 20 } },
  { path: '/institutions/:id', element: <Detail />, roles: ['institution', 'officer', 'authority'] },
  { path: '/institutions/:id/calculator', element: <Calculator />, roles: ['institution', 'officer', 'authority'] },
  { path: '/reports', element: <Reports />, roles: ['institution', 'officer', 'authority'],
    menu: { label: 'Reports', order: 21 } },
  { path: '/kpis', element: <Kpis />, roles: ['institution', 'officer', 'authority'],
    menu: { label: 'Process KPIs', order: 22 } },
  { path: '/imports/institutions', element: <Import />, roles: ['officer'],
    menu: { label: 'Import institutions', order: 23 } },
  { path: '/releases', element: <ReleaseCases />, roles: ['institution', 'officer', 'authority'],
    menu: { label: 'Release cases', order: 24 } },
  { path: '/releases/request', element: <ReleaseRequest />, roles: ['institution'] },
  { path: '/releases/:caseId', element: <ReleaseCase />, roles: ['institution', 'officer', 'authority', 'clearance'] },
  { path: '/clearance-tasks', element: <ClearanceQueue />, roles: ['clearance'],
    menu: { label: 'Clearance work', order: 25 } },
];

export const publicRoutes: AppRoute[] = [
  { path: '/verify/:token', element: <PublicVerification /> },
];
