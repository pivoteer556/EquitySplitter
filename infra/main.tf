resource "azurerm_resource_group" "main" {
  name     = "${var.name_prefix}-rg"
  location = var.location
  tags     = var.tags
}

# --- Container registry + pull identity ---
# Design choice: the Container App pulls via a USER-assigned identity with AcrPull, so
# no registry admin password exists anywhere (admin_enabled = false). User-assigned (not
# system-assigned) because the identity and its role must exist BEFORE the app is created,
# otherwise the first image pull fails.

resource "azurerm_container_registry" "main" {
  name                = "${replace(var.name_prefix, "-", "")}acr"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = var.tags
}

resource "azurerm_user_assigned_identity" "app" {
  name                = "${var.name_prefix}-id"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = var.tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# --- Container Apps environment ---

resource "azurerm_log_analytics_workspace" "main" {
  name                = "${var.name_prefix}-logs"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_container_app_environment" "main" {
  name                       = "${var.name_prefix}-env"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = var.tags
}

# --- PostgreSQL Flexible Server ---
# KNOWINGLY ACCEPTED RISK: public network access with the 0.0.0.0 "allow Azure services"
# firewall rule below. That admits any Azure-hosted client (any tenant), protected only by
# the admin password and TLS. Private networking (VNet + private DNS) is out of scope for
# the minimum change.

resource "azurerm_postgresql_flexible_server" "main" {
  name                   = "${var.name_prefix}-pg"
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  version                = "16"
  sku_name               = "B_Standard_B1ms"
  storage_mb             = 32768
  administrator_login    = var.postgres_admin_login
  administrator_password = var.postgres_admin_password
  tags                   = var.tags

  # Azure assigns an availability zone when none is given; without this, later plans
  # show a spurious zone diff.
  lifecycle {
    ignore_changes = [zone]
  }
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_postgresql_flexible_server_database" "app" {
  name      = var.postgres_database_name
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# --- Container App ---

locals {
  # sslmode=require: Flexible Server enforces TLS. urlencode keeps special characters in
  # the credentials from breaking the URL. Sensitive because it derives from a sensitive var.
  database_url = "postgresql+psycopg://${urlencode(var.postgres_admin_login)}:${urlencode(var.postgres_admin_password)}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${var.postgres_database_name}?sslmode=require"
}

# NOTE (step 2): the image does not exist in the registry until the first push, so the
# first `apply` must push the image first (e.g. apply the registry targeted, push, then
# apply the rest) or use a placeholder image. Not solved in this step (no apply happens).
resource "azurerm_container_app" "api" {
  name                         = "${var.name_prefix}-api"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.app.id
  }

  secret {
    name  = "database-url"
    value = local.database_url
  }

  secret {
    name  = "jwt-secret-seed"
    value = var.jwt_secret_seed
  }

  ingress {
    external_enabled = true
    target_port      = var.container_port

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "api"
      image  = "${azurerm_container_registry.main.login_server}/equity-splitter-api:${var.image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "APP_ENV"
        value = "prod"
      }
      env {
        name  = "TRUSTED_PROXY_HOPS"
        value = tostring(var.trusted_proxy_hops)
      }
      env {
        name  = "JWT_EXP_MINUTES"
        value = tostring(var.jwt_exp_minutes)
      }
      env {
        name  = "JWT_ROTATION_DAYS"
        value = tostring(var.jwt_rotation_days)
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "JWT_SECRET_SEED"
        secret_name = "jwt-secret-seed"
      }
    }
  }

  # The pull role must exist before the app tries to pull its image.
  depends_on = [azurerm_role_assignment.acr_pull]
}
