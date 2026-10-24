import { BankOutlined } from '@ant-design/icons';
import { lazy } from 'react';
import type { AppRoute } from '@/routes/types';

const List = lazy(() => import('./InstitutionPages').then(module => ({ default: module.InstitutionsPage })));
const Detail = lazy(() => import('./InstitutionPages').then(module => ({ default: module.InstitutionPage })));
const Calculator = lazy(() => import('./InstitutionPages').then(module => ({ default: module.InstitutionCalculatorPage })));

export const routes: AppRoute[] = [
  { path: '/institutions', element: <List />, roles: ['institution', 'officer', 'authority'],
    menu: { label: 'Institutions', icon: <BankOutlined />, order: 20 } },
  { path: '/institutions/:id', element: <Detail />, roles: ['institution', 'officer', 'authority'] },
  { path: '/institutions/:id/calculator', element: <Calculator />, roles: ['institution', 'officer', 'authority'] },
];
