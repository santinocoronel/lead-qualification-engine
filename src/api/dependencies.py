from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from src.api.middleware.api_key_auth import require_api_key
from src.application.use_cases.ingest_and_qualify_lead import IngestAndQualifyLeadUseCase
from src.infrastructure.config.settings import Settings
from src.infrastructure.crypto.fernet_utils import decrypt_value
from src.infrastructure.llm.llm_factory import create_analyzer
from src.infrastructure.persistence.client_model import ClientModel
from src.infrastructure.persistence.lead_repository import SQLAlchemyLeadRepository


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_use_case(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[ClientModel, Depends(require_api_key)],
) -> IngestAndQualifyLeadUseCase:
    session_factory = request.app.state.session_factory
    repository = SQLAlchemyLeadRepository(session_factory)

    provider = client.custom_llm_provider if client.encrypted_api_key else None
    decrypted_key = None
    if provider and client.encrypted_api_key and settings.fernet_key:
        decrypted_key = decrypt_value(client.encrypted_api_key, settings.fernet_key)

    llm_analyzer = create_analyzer(settings, provider, decrypted_key)

    return IngestAndQualifyLeadUseCase(
        repository=repository,
        llm_analyzer=llm_analyzer,
    )
