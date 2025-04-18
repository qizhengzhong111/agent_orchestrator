import json
import msal
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def get_secret_from_keyvault(key_vault_uri: str, secret_name: str) -> str:
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=key_vault_uri, credential=credential)
    secret = client.get_secret(secret_name)
    return secret.value

def acquire_user_access_token(config_path: str) -> str:
    with open(config_path, "r") as f:
        config = json.load(f)

    client_id = config["ClientId"]
    tenant_id = config["TenantId"]
    username = config["TestUserId"]
    key_vault_uri = config["KeyVaultUri"]
    password_secret_name = config["TestUserPasswordSecret"]
    scopes = config["ClientScopes"]

    # Securely get password from Key Vault
    password = get_secret_from_keyvault(key_vault_uri, password_secret_name)

    authority = f"https://login.microsoftonline.com/{tenant_id}"

    app = msal.PublicClientApplication(
        client_id=client_id,
        authority=authority,
    )

    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(scopes, account=accounts[0])
        if result and "access_token" in result:
            return result["access_token"]

    result = app.acquire_token_by_username_password(
        username=username,
        password=password,
        scopes=scopes
    )

    if "access_token" in result:
        return result["access_token"]
    else:
        raise Exception(f"Access token acquisition failed: {result.get('error_description')}")

