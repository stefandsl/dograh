"""Database access for Telegram SIP gateway configurations and call logs."""

from typing import Any, Dict, List, Optional

from sqlalchemy.future import select

from api.db.base_client import BaseDBClient
from api.db.models import TelegramSipCallLogModel, TelegramSipGatewayConfigurationModel


class TelegramSipGatewayClient(BaseDBClient):
    async def list_gateway_configurations(
        self, organization_id: int
    ) -> List[TelegramSipGatewayConfigurationModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(TelegramSipGatewayConfigurationModel)
                .where(
                    TelegramSipGatewayConfigurationModel.organization_id
                    == organization_id
                )
                .order_by(TelegramSipGatewayConfigurationModel.created_at)
            )
            return list(result.scalars().all())

    async def get_gateway_configuration(
        self, config_id: int
    ) -> Optional[TelegramSipGatewayConfigurationModel]:
        async with self.async_session() as session:
            return await session.get(TelegramSipGatewayConfigurationModel, config_id)

    async def get_gateway_configuration_for_org(
        self, config_id: int, organization_id: int
    ) -> Optional[TelegramSipGatewayConfigurationModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(TelegramSipGatewayConfigurationModel).where(
                    TelegramSipGatewayConfigurationModel.id == config_id,
                    TelegramSipGatewayConfigurationModel.organization_id
                    == organization_id,
                )
            )
            return result.scalars().first()

    async def create_gateway_configuration(
        self,
        *,
        organization_id: int,
        name: str,
        gateway_provider_type: str,
        credentials: Dict[str, Any],
        is_enabled: bool = True,
    ) -> TelegramSipGatewayConfigurationModel:
        async with self.async_session() as session:
            row = TelegramSipGatewayConfigurationModel(
                organization_id=organization_id,
                name=name,
                gateway_provider_type=gateway_provider_type,
                credentials=credentials,
                is_enabled=is_enabled,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def update_gateway_configuration(
        self,
        config_id: int,
        organization_id: int,
        *,
        name: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
        is_enabled: Optional[bool] = None,
        gateway_provider_type: Optional[str] = None,
    ) -> Optional[TelegramSipGatewayConfigurationModel]:
        async with self.async_session() as session:
            row = await session.get(TelegramSipGatewayConfigurationModel, config_id)
            if not row or row.organization_id != organization_id:
                return None
            if name is not None:
                row.name = name
            if credentials is not None:
                row.credentials = credentials
            if is_enabled is not None:
                row.is_enabled = is_enabled
            if gateway_provider_type is not None:
                row.gateway_provider_type = gateway_provider_type
            await session.commit()
            await session.refresh(row)
            return row

    async def delete_gateway_configuration(
        self, config_id: int, organization_id: int
    ) -> bool:
        async with self.async_session() as session:
            row = await session.get(TelegramSipGatewayConfigurationModel, config_id)
            if not row or row.organization_id != organization_id:
                return False
            await session.delete(row)
            await session.commit()
            return True

    async def create_call_log(
        self,
        *,
        organization_id: int,
        configuration_id: int,
        direction: str,
        destination: str,
        status: str = "initiated",
        gateway_call_id: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        events: Optional[List[Dict[str, Any]]] = None,
    ) -> TelegramSipCallLogModel:
        async with self.async_session() as session:
            row = TelegramSipCallLogModel(
                organization_id=organization_id,
                configuration_id=configuration_id,
                direction=direction,
                destination=destination,
                status=status,
                gateway_call_id=gateway_call_id,
                error_code=error_code,
                error_message=error_message,
                events=events or [],
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def update_call_log(
        self,
        call_log_id: int,
        organization_id: int,
        *,
        status: Optional[str] = None,
        gateway_call_id: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        append_event: Optional[Dict[str, Any]] = None,
    ) -> Optional[TelegramSipCallLogModel]:
        async with self.async_session() as session:
            row = await session.get(TelegramSipCallLogModel, call_log_id)
            if not row or row.organization_id != organization_id:
                return None
            if status is not None:
                row.status = status
            if gateway_call_id is not None:
                row.gateway_call_id = gateway_call_id
            if error_code is not None:
                row.error_code = error_code
            if error_message is not None:
                row.error_message = error_message
            if append_event is not None:
                events = list(row.events or [])
                events.append(append_event)
                row.events = events
            await session.commit()
            await session.refresh(row)
            return row

    async def get_call_log_for_org(
        self, call_log_id: int, organization_id: int
    ) -> Optional[TelegramSipCallLogModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(TelegramSipCallLogModel).where(
                    TelegramSipCallLogModel.id == call_log_id,
                    TelegramSipCallLogModel.organization_id == organization_id,
                )
            )
            return result.scalars().first()

    async def list_call_logs(
        self,
        organization_id: int,
        *,
        configuration_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[TelegramSipCallLogModel]:
        async with self.async_session() as session:
            query = (
                select(TelegramSipCallLogModel)
                .where(TelegramSipCallLogModel.organization_id == organization_id)
                .order_by(TelegramSipCallLogModel.created_at.desc())
                .limit(limit)
            )
            if configuration_id is not None:
                query = query.where(
                    TelegramSipCallLogModel.configuration_id == configuration_id
                )
            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_call_log_by_gateway_id(
        self, gateway_call_id: str, configuration_id: int
    ) -> Optional[TelegramSipCallLogModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(TelegramSipCallLogModel).where(
                    TelegramSipCallLogModel.gateway_call_id == gateway_call_id,
                    TelegramSipCallLogModel.configuration_id == configuration_id,
                )
            )
            return result.scalars().first()
