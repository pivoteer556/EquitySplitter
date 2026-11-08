import { Routes } from '@angular/router';
import { LoginPageComponent } from './login-page.component';
import { WorkbenchPageComponent } from './workbench-page.component';
import { AcceptInvitePageComponent } from './accept-invite-page.component';
import { ActivatePageComponent } from './activate-page.component';
import { ListingsPageComponent } from './listings-page.component';
import { authGuard, officerGuard } from './auth.guard';
import { BuyerPageComponent } from './buyer-page.component';

export const routes: Routes = [
  { path: 'login', component: LoginPageComponent },
  { path: 'buyer', component: BuyerPageComponent },
  { path: 'accept-invite', component: AcceptInvitePageComponent },
  { path: 'activate', component: ActivatePageComponent },
  { path: 'workbench', component: WorkbenchPageComponent, canActivate: [officerGuard] },
  { path: 'listings', component: ListingsPageComponent, canActivate: [authGuard] },
  { path: '', pathMatch: 'full', redirectTo: 'login' },
  { path: '**', redirectTo: 'login' },
];
