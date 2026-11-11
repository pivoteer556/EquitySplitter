import { Routes } from '@angular/router';
import { LoginPageComponent } from './login-page.component';
import { WorkbenchPageComponent } from './workbench-page.component';
import { AcceptInvitePageComponent } from './accept-invite-page.component';
import { ActivatePageComponent } from './activate-page.component';
import { ListingsPageComponent } from './listings-page.component';
import { authGuard, officerGuard } from './auth.guard';
import { BootstrapPageComponent } from './bootstrap-page.component';
import { SecurityPageComponent } from './security-page.component';
import { HomePageComponent } from './home-page.component';

export const routes: Routes = [
  { path: 'login', component: LoginPageComponent },
  { path: 'bootstrap', component: BootstrapPageComponent },
  { path: 'accept-invite', component: AcceptInvitePageComponent },
  { path: 'activate', component: ActivatePageComponent },
  { path: 'workbench', component: WorkbenchPageComponent, canActivate: [officerGuard] },
  { path: 'security', component: SecurityPageComponent, canActivate: [officerGuard] },
  { path: 'listings', component: ListingsPageComponent, canActivate: [authGuard] },
  { path: 'home', component: HomePageComponent, canActivate: [authGuard] },
  { path: '', pathMatch: 'full', redirectTo: 'login' },
  { path: '**', redirectTo: 'login' },
];
