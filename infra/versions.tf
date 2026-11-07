terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.81"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.8"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}

  subscription_id = var.subscription_id

  # The provider's automatic registration of ~12 unrelated resource providers (Compute,
  # HDInsight, ...) hung on a fresh subscription and does not include Microsoft.App anyway.
  # Register what this stack needs once, by hand:
  #   az provider register --namespace <ns> --wait
  # for Microsoft.App, Microsoft.DBforPostgreSQL, Microsoft.OperationalInsights,
  # Microsoft.ContainerRegistry, Microsoft.KeyVault, Microsoft.ManagedIdentity.
  resource_provider_registrations = "none"
}

# Tenant comes from the az CLI login; nothing hard-coded.
provider "azuread" {}
