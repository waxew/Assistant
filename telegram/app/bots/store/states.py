from aiogram.fsm.state import State, StatesGroup


class CustomerState(StatesGroup):
    search = State()
    tracking = State()
    support = State()
    topup_amount = State()
    topup_receipt = State()
    discount = State()
    manual_info = State()
    confirm = State()


class CategoryState(StatesGroup):
    add = State()
    rename = State()


class ProductCreateState(StatesGroup):
    name = State()
    slug = State()
    description = State()
    delivery_type = State()
    delivery_content = State()
    manual_prompt = State()
    category = State()
    photos = State()
    plan_name = State()
    plan_price = State()


class ProductEditState(StatesGroup):
    value = State()
    delivery_content = State()
    add_plan_name = State()
    add_plan_price = State()


class PlanEditState(StatesGroup):
    value = State()


class BulkPriceState(StatesGroup):
    value = State()


class DiscountState(StatesGroup):
    code = State()
    value = State()
    usage_limit = State()


class UserManageState(StatesGroup):
    user_id = State()
    balance = State()


class MessageManageState(StatesGroup):
    direct_user_id = State()
    direct_message = State()
    broadcast = State()
    forward = State()


class SettingsState(StatesGroup):
    value = State()
    channel = State()
