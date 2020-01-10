from functools import wraps

from schematics import Model
from schematics.types import UUIDType, StringType, ModelType, ListType, DateType, BaseType, DictType, IntType, \
    BooleanType, DataError
from schematics.types.base import TypeMeta
from flask import abort, request, Response, jsonify


class EnumMeta(TypeMeta):
    def __new__(mcs, name, bases, attrs):
        attrs['choices'] = [v for k, v in attrs.items() if not k.startswith('_') and k.isupper()]
        return TypeMeta.__new__(mcs, name, bases, attrs)


class ApproxDateType(DateType):
    formats = ['%Y-%m']


class DemoResultType(StringType):
    ANY = 'ANY'

    # Errors
    ERROR_INVALID_CREDENTIALS = 'ERROR_INVALID_CREDENTIALS'
    ERROR_ANY_PROVIDER_MESSAGE = 'ERROR_ANY_PROVIDER_MESSAGE'
    ERROR_CONNECTION_TO_PROVIDER = 'ERROR_CONNECTION_TO_PROVIDER'

    # Identity check specific
    NO_MATCHES = 'NO_MATCHES'
    ONE_NAME_ADDRESS_MATCH = 'ONE_NAME_ADDRESS_MATCH'
    ONE_NAME_DOB_MATCH = 'ONE_NAME_DOB_MATCH'
    TWO_NAME_ADDRESS_MATCHES = 'TWO_NAME_ADDRESS_MATCHES'
    ONE_NAME_ADDRESS_ONE_NAME_DOB_MATCH = 'ONE_NAME_ADDRESS_ONE_NAME_DOB_MATCH'
    ONE_NAME_ADDRESS_DOB_MATCH = 'ONE_NAME_ADDRESS_DOB_MATCH'
    MORTALITY_MATCH = 'MORTALITY_MATCH'
    ONE_NAME_ADDRESS_MORTALITY_MATCH = 'ONE_NAME_ADDRESS_MORTALITY_MATCH'
    ONE_NAME_ADDRESS_ONE_NAME_DOB_MORTALITY_MATCH = 'ONE_NAME_ADDRESS_ONE_NAME_DOB_MORTALITY_MATCH'


class CommercialRelationshipType(StringType, metaclass=EnumMeta):
    PASSFORT = 'PASSFORT'
    DIRECT = 'DIRECT'


class ErrorType(StringType, metaclass=EnumMeta):
    INVALID_CREDENTIALS = 'INVALID_CREDENTIALS'
    INVALID_CONFIG = 'INVALID_CONFIG'
    MISSING_CHECK_INPUT = 'MISSING_CHECK_INPUT'
    INVALID_CHECK_INPUT = 'INVALID_CHECK_INPUT'
    PROVIDER_CONNECTION = 'PROVIDER_CONNECTION'
    PROVIDER_MESSAGE = 'PROVIDER_MESSAGE'
    UNSUPPORTED_DEMO_RESULT = 'UNSUPPORTED_DEMO_RESULT'


class EntityType(StringType, metaclass=EnumMeta):
    INDIVIDUAL = 'INDIVIDUAL'


class AddressType(StringType, metaclass=EnumMeta):
    STRUCTURED = 'STRUCTURED'


class GenderType(StringType, metaclass=EnumMeta):
    MALE = 'M'
    FEMALE = 'F'


class EkycDatabaseType(StringType, metaclass=EnumMeta):
    CIVIL = 'CIVIL'
    CREDIT = 'CREDIT'
    MORTALITY = 'MORTALITY'
    IGNORED = 'IGNORED'


class EkycMatchField(StringType, metaclass=EnumMeta):
    FORENAME = 'FORENAME'
    SURNAME = 'SURNAME'
    ADDRESS = 'ADDRESS'
    DOB = 'DOB'
    IDENTITY_NUMBER = 'IDENTITY_NUMBER'
    IDENTITY_NUMBER_SUFFIX = 'IDENTITY_NUMBER_SUFFIX'


class ProviderConfig(Model):
    require_dob = BooleanType(required=True)
    mortality_check = BooleanType(required=True)
    requires_address_on_all_matches = BooleanType(required=True)
    run_original_address = BooleanType(required=True)
    whitelisted_databases = ListType(StringType)


class ProviderCredentials(Model):
    username = StringType(required=True)
    password = StringType(required=True)
    url = StringType(required=True)
    public_key = StringType(required=True)
    private_key = StringType(required=True)


class Error(Model):
    type = ErrorType(required=True)
    message = StringType(required=True)


class Warn(Model):
    type = ErrorType(required=True)
    message = StringType(required=True)


class FullName(Model):
    title = StringType(default=None)
    given_names = ListType(StringType, required=True)
    family_name = StringType(required=True, min_length=1)

    class Options:
        serialize_when_none = False


class PersonalDetails(Model):
    name = ModelType(FullName, required=True)
    dob = StringType(default=None)
    nationality = StringType(default=None)
    national_identity_number = DictType(StringType(), default=None)
    gender = GenderType(default=None)

    class Options:
        serialize_when_none = False


class StructuredAddress(Model):
    country = StringType(required=True)
    state_province = StringType(default=None)
    county = StringType(default=None)
    postal_code = StringType(default=None)
    locality = StringType(default=None)
    postal_town = StringType(default=None)
    route = StringType(default=None)
    street_number = StringType(default=None)
    premise = StringType(default=None)
    subpremise = StringType(default=None)
    address_lines = ListType(StringType(), default=None)

    class Options:
        serialize_when_none = False


class Address(StructuredAddress):
    type = AddressType(required=True, default=AddressType.STRUCTURED)
    original_freeform_address = StringType(default=None)
    original_structured_address = ModelType(StructuredAddress, default=None)


class DatedAddress(Model):
    address = ModelType(Address, required=True)
    start_date = ApproxDateType(default=None)
    end_date = ApproxDateType(default=None)

    class Options:
        serialize_when_none = False


class EkycExtraField(Model):
    name = StringType(required=True)
    value = StringType(default=None)


class EkycMatch(Model):
    database_name = StringType(required=True)
    database_type = EkycDatabaseType(required=True)
    matched_fields = ListType(EkycMatchField, required=True)
    date_first_seen = DateType(default=None)
    date_of_last_activity = DateType(default=None)
    extra = ListType(EkycExtraField, default=None)
    count = IntType(required=True, min_value=0)

    class Options:
        serialize_when_none = False


class ContactDetails(Model):
    phone_number = StringType(default=None)

    class Options:
        serialize_when_none = False


class ElectronicIdCheck(Model):
    matches = ListType(ModelType(EkycMatch), default=None)
    provider_reference_number = StringType(default=None)

    class Options:
        serialize_when_none = False


class IndividualData(Model):
    entity_type = EntityType(required=True, default=EntityType.INDIVIDUAL)
    personal_details = ModelType(PersonalDetails, default=None)
    address_history = ListType(ModelType(DatedAddress), default=None)
    contact_details = ModelType(ContactDetails, default=None)
    electronic_id_check = ModelType(ElectronicIdCheck, default=None)

    class Options:
        serialize_when_none = False


class RunCheckRequest(Model):
    id = UUIDType(required=True)
    demo_result = DemoResultType(default=None)
    commercial_relationship = CommercialRelationshipType(required=True)
    check_input = ModelType(IndividualData, required=True)
    provider_config = ModelType(ProviderConfig, required=True)
    provider_credentials = ModelType(ProviderCredentials, default=None)

    class Options:
        serialize_when_none = False


class RunCheckResponse(Model):
    check_output = ModelType(IndividualData, default=None)
    errors = ListType(ModelType(Error), default=[])
    warnings = ListType(ModelType(Warn), default=[])
    provider_data = BaseType(default=None)

    class Options:
        serialize_when_none = False


def validate_models(request_model, response_model):
    """
    Creates a Schematics Model from the request data and validates it.

    Throws DataError if invalid.
    Otherwise, it passes the validated request data to the wrapped function.
    """

    def validates_models(fn):
        @wraps(fn)
        def wrapped_fn(*args, **kwargs):
            model = None
            try:
                model = request_model().import_data(request.json, apply_defaults=True)
                model.validate()
            except DataError as e:
                abort(Response(str(e), status=400))

            res = fn(model, *args, **kwargs)

            assert isinstance(res, response_model)
            return jsonify(res.serialize())

        return wrapped_fn

    return validates_models
