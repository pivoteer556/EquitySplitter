# Generated secrets, Key Vault, and GitHub OIDC identity for the future deploy workflow.

# --- Generated secrets ---
# special = false: alembic/env.py breaks on `%` in DATABASE_URL, and alphanumeric values
# need no escaping anywhere (URLs, env vars). 32 alphanumerics is ~190 bits of entropy.
# KNOWINGLY ACCEPTED RISK: random_password values live in Terraform state in plain text
# (as do the Key Vault secret values). Protect the state; Key Vault is the runtime copy.
# Rotation: `terraform apply -replace=random_password.<name>`.

resource "random_password" "postgres_admin" {
  length  = 32
  special = false
}

resource "random_password" "jwt_secret_seed" {
  length  = 32 # JWT_SECRET_SEED must be >= 32 chars (formerly validated on the variable)
  special = false
}

# --- Key Vault ---

data "azurerm_client_config" "current" {}

# Key Vault names are global, 3-24 chars, start with a letter, alphanumerics and single
# hyphens. A short random suffix avoids collisions and soft-deleted-name clashes.
resource "random_string" "key_vault_suffix" {
  length  = 4
  special = false
  upper   = false
}

resource "azurerm_key_vault" "main" {
  # name_prefix may be up to 30 chars, so truncate to 15: 15 + "-kv-" (4) + suffix (4) = 23.
  # trim removes a trailing hyphen left by truncation (no "--" allowed in vault names).
  # Residual limit: a name_prefix with an inner "--" or a leading digit yields an invalid
  # vault name; the default prefix is fine.
  name                = "${trim(substr(var.name_prefix, 0, 15), "-")}-kv-${random_string.key_vault_suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"
  tags                = var.tags

  # RBAC instead of access policies (azurerm 4.x attribute name).
  rbac_authorization_enabled = true

  # Soft delete stays at its default (on, 90 days). Purge protection is left off so a
  # failed/abandoned deployment can be fully destroyed and re-created.
  # KNOWINGLY ACCEPTED RISK: public_network_access_enabled keeps its default (true);
  # access is still gated by Entra ID + RBAC. A private endpoint is out of scope.
}

# The applying identity must be able to write secrets. RBAC changes propagate with a
# delay, hence the explicit depends_on from each secret to this assignment.
resource "azurerm_role_assignment" "key_vault_applier" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_key_vault_secret" "postgres_admin_password" {
  name         = "postgres-admin-password"
  value        = random_password.postgres_admin.result
  key_vault_id = azurerm_key_vault.main.id
  tags         = var.tags

  depends_on = [azurerm_role_assignment.key_vault_applier]
}

resource "azurerm_key_vault_secret" "database_url" {
  name         = "database-url"
  value        = local.database_url
  key_vault_id = azurerm_key_vault.main.id
  tags         = var.tags

  depends_on = [azurerm_role_assignment.key_vault_applier]
}

# The Container App reads its secrets from Key Vault at runtime through its user-assigned
# identity (Key Vault references), so secret values are not stored in the app definition.
resource "azurerm_role_assignment" "app_key_vault_reader" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_key_vault_secret" "jwt_secret_seed" {
  name         = "jwt-secret-seed"
  value        = random_password.jwt_secret_seed.result
  key_vault_id = azurerm_key_vault.main.id
  tags         = var.tags

  depends_on = [azurerm_role_assignment.key_vault_applier]
}

# --- GitHub OIDC (no stored credentials) ---

resource "azuread_application" "github" {
  display_name = "${var.name_prefix}-github"
}

resource "azuread_service_principal" "github" {
  client_id = azuread_application.github.client_id
}

# Only workflows running on master of var.github_repository can obtain a token.
# Pull requests and other branches do not match this subject.
resource "azuread_application_federated_identity_credential" "github" {
  application_id = azuread_application.github.id
  display_name   = "github-master"
  issuer         = "https://token.actions.githubusercontent.com"
  audiences      = ["api://AzureADTokenExchange"]
  subject        = "repo:${var.github_repository}:ref:refs/heads/master"
}

# Least privilege for the deploy workflow: push images, and update the one Container App.
# Contributor is scoped to the app resource itself, not the resource group, so the
# pipeline cannot touch the database, Key Vault or registry settings.
resource "azurerm_role_assignment" "github_acr_push" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPush"
  principal_id         = azuread_service_principal.github.object_id
  principal_type       = "ServicePrincipal" # skips the AAD replication wait on fresh principals
}

resource "azurerm_role_assignment" "github_app_contributor" {
  scope                = azurerm_container_app.api.id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.github.object_id
  principal_type       = "ServicePrincipal"
}
