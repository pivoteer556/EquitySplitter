import { Routes } from '@angular/router';
import { LoginPageComponent } from './login-page.component';
import { WorkbenchPageComponent } from './workbench-page.component';
import { AcceptInvitePageComponent } from './accept-invite-page.component';
import { authGuard } from './auth.guard';

export const routes: Routes = [
  { path: 'login', component: LoginPageComponent },
  { path: 'accept-invite', component: AcceptInvitePageComponent },
  { path: 'workbench', component: WorkbenchPageComponent, canActivate: [authGuard] },
  { path: '', pathMatch: 'full', redirectTo: 'login' },
  { path: '**', redirectTo: 'login' },
];
