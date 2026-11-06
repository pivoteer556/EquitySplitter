import { Routes } from '@angular/router';
import { LoginPageComponent } from './login-page.component';
import { WorkbenchPageComponent } from './workbench-page.component';
import { authGuard } from './auth.guard';

export const routes: Routes = [
  { path: 'login', component: LoginPageComponent },
  { path: 'workbench', component: WorkbenchPageComponent, canActivate: [authGuard] },
  { path: '', pathMatch: 'full', redirectTo: 'login' },
  { path: '**', redirectTo: 'login' },
];
