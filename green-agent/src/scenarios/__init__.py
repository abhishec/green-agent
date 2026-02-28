from .task_01_order import Task01OrderScenario
from .task_02_procurement import Task02ProcurementScenario
from .task_03_offboarding import Task03OffboardingScenario
from .task_04_insurance import Task04InsuranceScenario
from .task_05_invoice import Task05InvoiceScenario
from .task_06_sla import Task06SlaScenario
from .task_07_travel import Task07TravelScenario
from .task_08_compliance import Task08ComplianceScenario
from .task_09_subscription import Task09SubscriptionScenario
from .task_10_dispute import Task10DisputeScenario
from .task_11_accounting import Task11AccountingScenario
from .task_12_product import Task12ProductScenario
from .task_13_ar import Task13ArScenario
from .task_14_incident import Task14IncidentScenario
from .task_15_qbr import Task15QbrScenario
from .task_16_retail_return import Task16RetailReturnScenario
from .task_17_retail_cancel import Task17RetailCancelScenario
from .task_18_retail_exchange import Task18RetailExchangeScenario
from .task_19_retail_modify import Task19RetailModifyScenario
from .task_20_retail_address import Task20RetailAddressScenario
from .task_21_airline_booking import Task21AirlineBookingScenario
from .task_22_airline_change import Task22AirlineChangeScenario
from .task_23_airline_cancel import Task23AirlineCancelScenario

SCENARIO_REGISTRY: dict[str, type] = {
    "task_01": Task01OrderScenario,
    "task_02": Task02ProcurementScenario,
    "task_03": Task03OffboardingScenario,
    "task_04": Task04InsuranceScenario,
    "task_05": Task05InvoiceScenario,
    "task_06": Task06SlaScenario,
    "task_07": Task07TravelScenario,
    "task_08": Task08ComplianceScenario,
    "task_09": Task09SubscriptionScenario,
    "task_10": Task10DisputeScenario,
    "task_11": Task11AccountingScenario,
    "task_12": Task12ProductScenario,
    "task_13": Task13ArScenario,
    "task_14": Task14IncidentScenario,
    "task_15": Task15QbrScenario,
    "task_16": Task16RetailReturnScenario,
    "task_17": Task17RetailCancelScenario,
    "task_18": Task18RetailExchangeScenario,
    "task_19": Task19RetailModifyScenario,
    "task_20": Task20RetailAddressScenario,
    "task_21": Task21AirlineBookingScenario,
    "task_22": Task22AirlineChangeScenario,
    "task_23": Task23AirlineCancelScenario,
}
