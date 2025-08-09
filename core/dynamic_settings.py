from dynamic_preferences.registries import global_preferences_registry
from dynamic_preferences.types import BooleanPreference

from dynamic_settings.enums import Sections
from dynamic_settings.preference_types import NonnegativeIntegerPreference


@global_preferences_registry.register
class AllowedExternalAccountsPerUser(NonnegativeIntegerPreference):
    section = Sections.resource_limit.value
    name = 'allowed_external_accounts_per_user'
    default = 5
    verbose_name = 'Allowed External Accounts Per User'
    help_text = "Number of external accounts that can be created by a user"


@global_preferences_registry.register
class AllowedInvitationTokensPerUser(NonnegativeIntegerPreference):
    section = Sections.resource_limit.value
    name = 'allowed_invitation_tokens_per_user'
    default = 5
    verbose_name = 'Allowed Invitation Tokens Per User'
    help_text = "Number of invitation tokens that can be created by a user"


@global_preferences_registry.register
class AdminApprovalRequiredForBDUser(BooleanPreference):
    section = Sections.onboarding.value
    name = 'manual_admin_approval_required'
    default = True
    verbose_name = 'Is Manual Admin Approval required for BD user'
    help_text = "Is manual admin approval required for BD user during onboarding"


@global_preferences_registry.register
class AdminApprovalRequiredForUSUser(BooleanPreference):
    section = Sections.onboarding.value
    name = 'admin_approval_required_for_us_user'
    default = True
    verbose_name = 'Is Manual Admin Approval required for US User'
    help_text = "Is manual admin approval required for US user during onboarding"


