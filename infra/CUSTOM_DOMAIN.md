# Custom domain (equitysplitter.app)

Goal: `https://equitysplitter.app` (Angular app) and `https://equitysplitter.app/hireme` (resume) are served by the
Static Web App over HTTPS with a free Azure managed certificate. Cost: free (Free tier). Terraform adds
`azurerm_static_web_app_custom_domain.web` (`validation_type = "dns-txt-token"`, the only type allowed for an apex
domain) and adds `https://equitysplitter.app` to the API's `CORS_ALLOW_ORIGINS` (the default hostname stays).

Provider behaviour (azurerm docs): TXT validation is asynchronous, so `terraform apply` does not wait for or fail on
a missing TXT record. It creates the resource and exposes `validation_token`; the token is empty once validated.

## Steps

1. Run `terraform apply` in `infra/` (you run it). It creates the custom domain (status "validating") and updates
   the Container App's CORS setting.
2. Read the values: `terraform output -raw custom_domain_txt_token` and
   `terraform output -raw custom_domain_cname_target`. Terraform hides the token in plan/apply output because the
   provider marks it sensitive; `-raw` prints it anyway.
3. In Cloudflare DNS for `equitysplitter.app`, add (both **DNS only**, grey cloud, NOT proxied; a proxied record
   stops Azure validating and issuing the certificate):

   | Type  | Name | Content                                           | Proxy    |
   | ----- | ---- | ------------------------------------------------- | -------- |
   | TXT   | `@`  | the `custom_domain_txt_token` value               | n/a      |
   | CNAME | `@`  | the `custom_domain_cname_target` value (no https) | DNS only |

   Cloudflare flattens a CNAME at the apex automatically, so no ALIAS record is needed.
4. Wait. Azure checks the TXT record, then issues the certificate. Usually minutes, up to 72 hours per Microsoft.
   Watch Azure portal > the Static Web App > Custom domains until the status is "Ready".
5. Verify: `curl -I https://equitysplitter.app/hireme` returns `200` over HTTPS, then open
   `https://equitysplitter.app` and sign in with the demo login (the API must accept the new origin; that
   is the CORS change from step 1).
6. If `terraform plan` later shows `validation_token` drift, ignore it; the token clears after validation.

`.app` is on the HSTS preload list, so browsers only use HTTPS; that is fine here.

## Roll back

Delete the `azurerm_static_web_app_custom_domain.web` resource and the `custom_domain` CORS entry from `main.tf`,
run `terraform apply`, then delete the TXT and CNAME records in Cloudflare.

## After it works

Done on 2026-11-11 for the resume page (`/hireme`) only: its demo links now use
`https://equitysplitter.app`. The repository README has no link to the old address, so nothing to change there.
The old default `azurestaticapps.net` address still works.

## Verification status

Verified in public docs: resource arguments, apex requires `dns-txt-token`, async validation, token attribute,
Cloudflare/Azure apex CNAME-flattening guidance. Untested: the real apply, certificate issuance time, and
Cloudflare record handling; those need your `terraform apply` and DNS changes.
