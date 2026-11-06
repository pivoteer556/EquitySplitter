# Only what step 2 (build/push/deploy) needs. No secrets.

output "resource_group_name" {
  value = azurerm_resource_group.main.name
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
