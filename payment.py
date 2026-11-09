import asyncio
from decimal import Decimal

from yoomoney import AsyncClient, Quickpay

import config


class YoomoneyAPI:
    async def is_success_operation(self, label: str, minimum_received: Decimal) -> bool:
        async with asyncio.timeout(20), AsyncClient(token=config.YOOMONEY_TOKEN) as client:
            history = await client.operation_history(label=label, records=100)
            for operation in history.operations:
                if (
                    operation.label == label
                    and operation.status == "success"
                    and operation.direction == "in"
                    and operation.amount is not None
                    and Decimal(str(operation.amount)).is_finite()
                    and Decimal(str(operation.amount)) >= minimum_received
                ):
                    return True
        return False

    def create_quickpay_url(self, amount: Decimal, label: str) -> dict[str, str]:
        quickpay = Quickpay(
            receiver=config.YOOMONEY_RECEIVER,
            quickpay_form="button",
            targets="PaymentsCloud",
            paymentType="AC",
            sum=amount,
            label=label,
        )
        quickpay.response.raise_for_status()
        return {"base_url": quickpay.base_url, "redirected_url": quickpay.redirected_url}
