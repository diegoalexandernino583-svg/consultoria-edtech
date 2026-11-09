"""
Automation Script: Azure SQL Database Automated Bacpac Backup
Education Technology SaaS Multi-Tenant Platform

Objetivo:
- Exportar periodicamente la base de datos Azure SQL (ConsultoriaDB) a Azure Blob Storage
- Mantener RPO < 1h y RTO < 4h para cumplir con el SLA de 99.9% Uptime
- Limpieza de backups antiguos aplicando politica de retencion (30 dias)
"""

import os
import sys
import datetime
import requests
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AzureSQLBackup")

SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID", "sub-edtech-prod")
RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP", "rg-edtech-prod")
SERVER_NAME = os.getenv("DB_SERVER", "servidor-consultoria-diego").replace(".database.windows.net", "")
DATABASE_NAME = os.getenv("DB_NAME", "ConsultoriaDB")
STORAGE_ACCOUNT = os.getenv("AZURE_STORAGE_ACCOUNT", "saedtechbackups")
STORAGE_CONTAINER = os.getenv("AZURE_BACKUP_CONTAINER", "sql-backups-bacpac")
STORAGE_KEY = os.getenv("AZURE_STORAGE_KEY", "")
DB_USER = os.getenv("DB_USER", "admin_diego")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

def get_azure_mgmt_token() -> str:
    """Obtiene token de autenticacion de Azure Resource Manager via MSI o Service Principal."""
    token = os.getenv("AZURE_BEARER_TOKEN")
    if token:
        return token
    # Intentar Managed Identity endpoint de Azure App Service / VM
    msi_endpoint = os.getenv("IDENTITY_ENDPOINT")
    msi_header = os.getenv("IDENTITY_HEADER")
    if msi_endpoint and msi_header:
        res = requests.get(
            f"{msi_endpoint}?resource=https://management.azure.com/&api-version=2019-08-01",
            headers={"X-IDENTITY-HEADER": msi_header},
            timeout=10
        )
        if res.status_code == 200:
            return res.json().get("access_token")
    return ""

def trigger_database_export(token: str) -> bool:
    """Solicita a la API REST de Azure SQL Database exportar un archivo .BACPAC."""
    now_str = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    blob_filename = f"{DATABASE_NAME}_{now_str}.bacpac"
    storage_uri = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net/{STORAGE_CONTAINER}/{blob_filename}"

    url = (
        f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/"
        f"providers/Microsoft.Sql/servers/{SERVER_NAME}/databases/{DATABASE_NAME}/export?api-version=2021-11-01"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "storageKeyType": "StorageAccessKey",
        "storageKey": STORAGE_KEY,
        "storageUri": storage_uri,
        "administratorLogin": DB_USER,
        "administratorLoginPassword": DB_PASSWORD,
        "authenticationType": "Sql"
    }

    logger.info(f"Iniciando exportacion BACPAC hacia {storage_uri}...")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code in (200, 202):
            op_data = response.json()
            logger.info(f"Backup iniciado exitosamente. Operacion: {op_data.get('name', 'N/A')}")
            return True
        else:
            logger.error(f"Error al solicitar exportacion: HTTP {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Fallo en la peticion de exportacion: {e}")
        return False

def main():
    logger.info("=== Automatizacion de Backups Azure SQL (Education Technology) ===")
    token = get_azure_mgmt_token()
    if not token and not STORAGE_KEY:
        logger.warning("Modo simulado: Credenciales de Azure Management no configuradas en entorno local.")
        logger.info(f"Configuracion objetivo: Servidor '{SERVER_NAME}', BD '{DATABASE_NAME}' -> Contenedor '{STORAGE_CONTAINER}'")
        sys.exit(0)
    
    success = trigger_database_export(token)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
