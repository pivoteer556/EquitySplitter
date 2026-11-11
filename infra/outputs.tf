# Only what step 2 (build/push/deploy) and frontend hosting need. The only secret is
# static_web_app_api_key (sensitive).

output "resource_group_name" {
  value = data.azurerm_resource_group.main.name
}

output "acr_name" {
  value = azurerm_container_registry.main.name
}

output "acr_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "container_app_name" {
  value = azurerm_container_app.api.name
}

output "container_app_url" {
  value = "https://${azurerm_container_app.api.ingress[0].fqdn}"
}

# Non-secret values for the GitHub repo variables used by the deploy workflow.
output "tenant_id" {
  value = data.azurerm_client_config.current.tenant_id
}

output "subscription_id" {
  value = var.subscription_id
}

output "github_client_id" {
  value = azuread_application.github.client_id
}

output "key_vault_name" {
  value = azurerm_key_vault.main.name
}

output "static_web_app_name" {
  value = azurerm_static_web_app.web.name
}

output "static_web_app_url" {
  value = "https://${azurerm_static_web_app.web.default_host_name}"
}

# The one secret output: the Static Web Apps deployment token, to be copied into a GitHub
# secret. Read it with `terraform output -raw static_web_app_api_key`. It is also in state.
output "static_web_app_api_key" {
  value     = azurerm_static_web_app.web.api_key
  sensitive = true
}

# The setup token for creating institutions. Read it with `terraform output -raw bootstrap_token`.
# It is also in state and Key Vault.
output "bootstrap_token" {
  value     = random_password.bootstrap_token.result
  sensitive = true
}

# DNS records to create for the custom domain (see infra/CUSTOM_DOMAIN.md). The token is empty
# once Azure has validated the domain.
output "custom_domain_txt_token" {
  value = azurerm_static_web_app_custom_domain.web.validation_token
}

output "custom_domain_cname_target" {
  value = azurerm_static_web_app.web.default_host_name
}
