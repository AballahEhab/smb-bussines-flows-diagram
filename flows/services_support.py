"""Source-checked subscription, support, order and alternate-entry journeys.

Only current navigation producers are promoted to screen edges. Empty dispatcher
branches and vendor-only destinations are represented explicitly as unresolved.
"""
from pathlib import Path
import re
from scripts.flow_builder import ROOTS


class Author:
    def __init__(self, builder):
        self.b = builder
        self.files = {}

    def ev(self, scope, needle, repo='F'):
        key = (repo, scope)
        if key not in self.files:
            root = ROOTS[repo] / scope
            self.files[key] = sorted(root.rglob('*')) if root.is_dir() else [root]
        for file in self.files[key]:
            if file.suffix not in ('.dart', '.kt', '.java', '.swift', '.m', '.h'):
                continue
            path = str(file.relative_to(ROOTS[repo]))
            lines = self.b.text(repo, path).splitlines()
            for line, value in enumerate(lines, 1):
                clean = value.strip()
                if needle in value and not clean.startswith(('import ', '//', '*', 'class ', '@interface')):
                    if needle.endswith('(') and needle[:1].isupper() and needle + '{' in value:
                        continue  # constructor declaration, not a navigation producer
                    return {'repo': repo, 'path': path, 'line': line, 'excerpt': clean[:350]}
        raise ValueError(f'Missing navigation evidence {repo}:{scope}:{needle}')

    def f(self, name, hint='', **kw):
        return self.b.f(name, hint, **kw)

    def edge(self, source, target, scope, needle, label, condition='', repo='F', kind='navigation', notes=''):
        return self.b.edge(source, target, label, [self.ev(scope, needle, repo)],
                           condition=condition, kind=kind, notes=notes)

    def entry(self, node):
        self.b.entry(node)
        return node


def build(b):
    a = Author(b)
    sect = 'lib/app/sections/'
    saas = sect + 'saas/'
    ref = sect + 'saas_refactor/saas_services/'
    domain = sect + 'domain_activation_management/'
    voice = sect + 'voice_line/'
    support = sect + 'help_and_support/'
    orders = sect + 'tracking_order/'
    subscriptions = sect + 'dashboard/account/subscriptions/'
    menu = sect + 'bss/support_menu/views/widgets/support_menu_success_widget.dart'
    android = 'app/src/main/java/ae/etisalat/smb/presentation/'
    ah = android + 'flutter/FlutterNavigationHandler.kt'
    ilink = 'FlutterFW/FlutterFW/Core/FlutterLink/'

    b.journey('subscriptions', 'Subscriptions and SaaS services', 'Subscriptions',
              'Eligible subscription menus and BFM account subscriptions; service choices are backend driven.')
    individual = a.entry(a.f('IndividualManageScreen'))
    listing = a.f('SubscriptionListScreen')
    party = a.f('PartyIdSearchScreen', 'domain_activation_management/party_id_search')
    accounts = a.f('AccountsListScreen', 'saas/commons/accounts')
    cardinality = a.f('SaasCardinalityScreen')
    web = a.f('SaasCommonWebViewScreen')
    account_content = a.entry(a.f('DashboardSubscriptionWidget', 'account/subscriptions', kind='content'))
    common = a.f('SaasServicesCommonScreen', 'saas/saas_services/common')
    parablu = a.f('ParaBluScreen', 'saas/saas_services/common')
    office = a.f('Office365StepsView')
    estore = a.f('ActivateEStoreScreen')
    a.edge(individual, listing, sect + 'individual_manage', 'SubscriptionCoordinator(', 'Subscriptions menu', 'Returned subscription menu permits SaaS')
    a.edge(listing, web, saas + 'commons/subscription/coordinator', 'SaasCommonWebViewScreen(', 'Firewall redirect', 'menu.menuId == firewallMenuId')
    a.edge(listing, party, saas + 'commons/subscription/coordinator', 'PartySelectionCoordinator(', 'Choose company', 'Other SaaS menu selected')
    a.edge(party, accounts, domain + 'party_id_search', 'AccountsCoordinator(', 'Choose eligible SaaS account', 'Selected service is neither domain nor direct voice line')
    a.edge(accounts, cardinality, saas + 'commons/accounts/coordinator', 'SaasCardinalityCoordinator(', 'Cardinality service', 'menuId == saasCardinalityMenuId')
    a.edge(account_content, cardinality, subscriptions, 'SaasCardinalityCoordinator(', 'Account cardinality service', 'menuId == saasCardinalityMenuId')
    dispatch_ev = a.ev(saas + 'commons/subscription_details/coordinator/subscription_details_coordinator.dart', 'serviceHandlers =')
    dispatch = b.decision('service', 'Which subscription service?', 'Selected menu ID and entry point (Manage vs account)', [dispatch_ev])
    a.edge(accounts, dispatch, saas + 'commons/accounts/coordinator', 'SubscriptionDetailsCoordinator(', 'Service details', 'Non-cardinality menu')
    a.edge(account_content, dispatch, subscriptions, 'SubscriptionDetailsCoordinator(', 'Account service details', 'Non-cardinality menu')
    a.edge(cardinality, dispatch, sect + 'saas_refactor/saas_cardinality', 'SubscriptionDetailsCoordinator(', 'Activate selected cardinality service', 'A service and quantity are selected')
    helper = saas + 'commons/subscription_details/coordinator/saas_coordinator_helper.dart'
    a.edge(dispatch, common, helper, 'SaasServicesCommonCoordinator(', 'Common SaaS form', 'Firewall / DGTx / Adverit / EMR / FSecure / CloudTalk / MegaImpex / Tawasal / Aleria; non-ParaBlu common menu')
    a.edge(dispatch, parablu, saas + 'saas_services/common/coordinator', 'ParaBluScreen(', 'ParaBlu common form', 'subscriptionId == paraBluMenuId')
    a.edge(dispatch, office, saas + 'commons/subscription_details/coordinator', 'Office365StepsCoordinator(', 'Office 365', 'menuId == office365MenuId; account entry2')
    a.edge(dispatch, estore, helper, 'ActivateEStoreCoordinator(', 'eStore service', 'menuId == eStoreMenuId')
    stub = b.unresolved('empty-dispatch', 'No screen: account Domain / generic Voice dispatcher',
                        [a.ev(saas + 'commons/subscription_details/coordinator/subscription_details_coordinator.dart', 'Widget prepareScreenDomainActivationEntryPoint2'),
                         a.ev(saas + 'commons/subscription_details/coordinator/subscription_details_coordinator.dart', 'Widget prepareScreenVoiceLineEntryPoint2')],
                        notes='Domain entry2 and voice entry2 return SizedBox.shrink; voice entry1 is empty. Direct domain/voice callers are separate working journeys.')
    b.edge(dispatch, stub, 'Incomplete service handler', [dispatch_ev], condition='Domain account entry2 or generic voice dispatcher')
    for source in [common, parablu, estore]:
        for symbol, outcome in [('SubmitSubscriptionSuccessScreen', 'Success'), ('SubmitSubscriptionFailureScreen', 'Failure')]:
            target = a.f(symbol, 'saas/commons/submit_subscription')
            caller = saas + ('e_store/activate_e_store/coordinator' if source == estore else 'saas_services/common/domain/viewmodel')
            b.edge(source, target, outcome + ' result',
                   [a.ev(caller, 'SubmitSubscriptionCoordinator('), a.ev(saas + 'commons/submit_subscription/coordinator/submit_subscription_coordinator.dart', symbol + '(')],
                   condition='Submit response indicates ' + outcome.lower())
    b.note('ManageEStoreScreen has an implementation but no current ManageEStoreCoordinator producer beyond its declaration; keep it caller-unconfirmed rather than invent an activation-to-management edge.')
    browser = b.service('vendor-web', 'Service / external subscription website', [a.ev(saas + 'commons/subscription/coordinator', 'webUrl:')], notes='URL supplied by backend; browser content is not a fixed app-screen inventory.')
    b.edge(web, browser, 'Open vendor content', [a.ev(saas + 'commons/subscription/coordinator', 'webUrl:')], kind='service')
    b.note('Office 365 named routes saasSteps and saasOfficeValidation resolve to the new Office365StepsView. Old StepsScreen / ValidateDomain / reseller chain remains caller-unconfirmed and is excluded from active screen edges.')
    b.note('Native SaaS adapters exist, but adapter registration alone is not a launch root; actual Manage/account producers above establish reachability.')

    b.journey('office365', 'Office 365 activation and domain consent', 'Subscriptions', 'New current Office 365 flow; API action states choose the next screen.')
    steps = a.entry(a.f('Office365StepsView'))
    choice = a.f('Office365DomainChoiceView')
    terms = a.f('Office365TermsAndConditionsView')
    consent = a.f('Office365MicrosoftCustomerConsentView')
    subdomain = a.f('Office365SubDomainView')
    reseller = a.f('Office365ChangeResellerView')
    unavailable = a.f('Office365DomainOwnershipUnavailableView')
    checkout = a.f('Office365CheckoutView')
    success = a.f('Office365CheckoutSuccessView')
    validation = a.f('Office365DomainChoiceValidationView', kind='content')
    office_root = ref + 'office_365/'
    a.edge(steps, choice, office_root + 'office_365_steps', 'Office365DomainChoiceCoordinator(', 'Continue setup')
    a.edge(choice, terms, office_root + 'office_365_domain_choice', 'Office365TermsAndConditionsCoordinator(', 'Read terms')
    a.edge(choice, consent, office_root + 'office_365_domain_choice/views', 'Office365MicrosoftCustomerConsentCoordinator(', 'Microsoft customer consent', 'consentAction.type == openConsent')
    a.edge(choice, subdomain, office_root + 'office_365_domain_choice/views', 'Office365SubDomainCoordinator(', 'Check existing-domain reseller', 'consentAction.type == navigateToReseller')
    a.edge(subdomain, reseller, office_root + 'office_365_sub_domain/coordinator', 'Office365ChangeResellerCoordinator(', 'Change reseller', 'Backend domain/reseller response permits reseller change')
    a.edge(subdomain, unavailable, office_root + 'office_365_sub_domain/coordinator', 'Office365DomainOwnershipUnavailableCoordinator(', 'Ownership unavailable', 'Backend ownership check fails')
    a.edge(reseller, subdomain, office_root + 'office_365_change_reseller/views', 'Office365SubDomainCoordinator(', 'Check reseller again', 'User continues reseller-change flow')
    a.edge(choice, validation, office_root + 'office_365_domain_choice/views', 'Office365DomainChoiceValidationView(', 'Domain validation content', 'Success content state renders validation')
    a.edge(reseller, validation, office_root + 'office_365_change_reseller/views', 'Office365DomainChoiceValidationView(', 'Validation content', 'Validation state selected')
    a.edge(choice, checkout, office_root + 'office_365_domain_choice/views', 'Office365CheckoutCoordinator(', 'Proceed to checkout', 'Success state shouldNavigateToCheckout == true')
    a.edge(checkout, success, office_root + 'office_365_checkout/views', 'Office365CheckoutSuccessView(', 'Activation complete', 'Checkout action succeeds')
    b.note('Domain exists, invalid domain and generic-error actions show a Flutter error bottom sheet on Domain Choice, not mandatory next screens. Returning from consent marks consent accepted; ownership/reseller branches remain conditional.')

    b.journey('domains', 'Domain activation and management', 'Subscriptions', 'Working direct company/account domain paths; generic SaaS account dispatcher is a separate no-op.')
    party = a.entry(a.f('PartyIdSearchScreen', 'domain_activation_management/party_id_search'))
    ac = a.entry(a.f('DashboardSubscriptionWidget', 'account/subscriptions', kind='content'))
    detail = a.f('DomainDetailScreen')
    steps = a.f('DomainStepsScreen')
    manage = a.f('ManageDomainScreen')
    validation = a.f('DomainValidationScreen')
    checkout = a.f('DomainCheckoutScreen')
    success = a.f('SuccessScreen', 'domain_activation_management/success')
    failure = a.f('DomainActivationErrorScreen')
    a.edge(party, detail, domain + 'party_id_search', 'DomainDetailScreen(', 'Domain service selected', 'saasMenuModel.menuId == domainMenuId')
    a.edge(detail, steps, domain + 'domain_detail', 'DomainStepsScreen(', 'Activate domain', 'Domain status allows activation')
    a.edge(detail, manage, domain + 'domain_detail', 'ManageDomainScreen(', 'Manage existing domain', 'Domain status selects management')
    a.edge(ac, steps, subscriptions, 'DomainStepsScreen(', 'Activate account domain', 'Account subscription activation action')
    a.edge(ac, manage, subscriptions, 'ManageDomainScreen(', 'Manage account domain', 'Account domain-management action')
    a.edge(manage, steps, domain + 'manage_domain', 'DomainStepsScreen(', 'Modify domain')
    a.edge(steps, validation, domain + 'domain_step', 'DomainValidationScreen(', 'Validate selected domain', 'Domain choice / validation action')
    a.edge(validation, checkout, domain + 'domain_validation', 'DomainCheckoutScreen(', 'Continue checkout', 'Domain validation response permits purchase')
    for source, scope in [(validation, domain + 'domain_validation'), (checkout, domain + 'domain_checkout')]:
        a.edge(source, success, scope, 'SuccessScreen(', 'Domain activation success', 'Activation/checkout response succeeds')
        a.edge(source, failure, scope, 'DomainActivationErrorScreen(', 'Activation error', 'Activation response fails')
    b.note('DomainListingScreen/DomainPromocodeScreen are not promoted solely because they exist; the current direct party/account path above is verified. Native domainAccounts adapter has a separately registered DomainDetailScreen boundary.')

    b.journey('parablu', 'ParaBlu plan management and purchase', 'Subscriptions', 'Direct account ParaBlu branch; common SaaS ParaBlu form is shown in Subscriptions.')
    ac = a.entry(a.f('DashboardSubscriptionWidget', 'account/subscriptions', kind='content'))
    detail = a.f('ParabluDetailsScreen')
    listing = a.f('ParabluServicesListingScreen')
    plan = a.f('AddonManagePlanScreen', 'parablu')
    form = a.f('ParabluSubscriptionDynamicFormScreen')
    form_content = a.f('FormLoadedScreen', 'parablu', kind='content')
    check = a.f('CheckoutScreen', 'sections/common')
    success = a.f('SubmitSubscriptionSuccessScreen', 'saas/commons')
    a.edge(ac, detail, subscriptions, 'ParabluDetailsCoordinator(', 'ParaBlu subscription action')
    a.edge(detail, listing, ref + 'parablu/parablu_details', 'ParabluServicesListingCoordinator(', 'View subscriptions / change plan')
    a.edge(listing, plan, ref + 'parablu/parablu_services_listing', 'ParabluManagePlanCoordinatoor(', 'Manage selected plan', 'Selected subscription is a valid plan')
    benefits = a.entry(a.f('AddonBenefitsScreen', 'addons/addons_benefets'))
    a.edge(benefits, form, sect + 'addons/addons_benefets', 'ParabluSubscriptionDynamicFormCoordinator(', 'Purchase ParaBlu add-on', 'ParaBlu add-on purchase branch')
    a.edge(form, form_content, ref + 'parablu', 'FormLoadedScreen(', 'Render backend form', 'Form state loaded')
    a.edge(plan, check, ref + 'parablu/parablu_manage_plan', 'CheckoutCoordinator(', 'Checkout plan change')
    a.edge(form, check, ref + 'parablu/parablu_subscription', 'CheckoutCoordinator(', 'Checkout new add-on')
    a.edge(plan, success, ref + 'parablu/parablu_manage_plan', 'SubmitSubscriptionSuccessScreen(', 'Plan update success', 'Modify subscription response succeeds')
    for symbol in ['DeletePlanBody', 'ConfirmDeletePlanBody', 'NotValidItemBody']:
        node = a.f(symbol, 'parablu', kind='sheet')
        ev = a.ev(ref + 'parablu', symbol + '(')
        b.edge(listing if symbol == 'NotValidItemBody' else detail, node, 'Plan confirmation / restriction', [ev], condition='Delete action or invalid-plan backend eligibility branch')
    b.note('Checkout is a shared Flutter flow; payment SDK is a service and does not change screen ownership. Deletion confirmation and invalid-plan sheets are optional, not a linear purchase sequence.')

    b.journey('voice-lines', 'Voice lines: buy, view and assign', 'Subscriptions', 'Direct subscriptions and company-menu callers; generic SaaS voice dispatcher is empty.')
    party = a.entry(a.f('PartyIdSearchScreen', 'domain_activation_management/party_id_search'))
    ac = a.entry(a.f('DashboardSubscriptionWidget', 'account/subscriptions', kind='content'))
    accounts = a.f('AccountsForVoiceLineScreen')
    listing = a.f('VoiceLineListScreen')
    ev_static = a.ev(voice + 'common/voice_line_static_content/coordinator', 'switch (flowOpenedFrom)')
    route = b.decision('origin', 'Choose voice-line entry', 'subscriptionMenus → account choice; subscriptionTab → selected account list', [ev_static])
    a.edge(party, route, domain + 'party_id_search', 'VoiceLineStaticContentCoordinator(', 'Voice-line menu selected', 'menuId == voiceLineMenuId')
    a.edge(ac, route, subscriptions, 'VoiceLineStaticContentCoordinator(', 'Account voice-line subscriptions')
    a.edge(route, accounts, voice + 'common/voice_line_static_content', 'AccountForVoiceLineCoordinator(', 'Choose account', 'subscriptionMenus and linkedPartyAccounts != null')
    a.edge(route, listing, voice + 'common/voice_line_static_content', 'VoiceLineListCoordinator(', 'Use selected account', 'subscriptionTab and selectedAccount != null')
    a.edge(accounts, listing, voice + 'manage_voice_line/accounts_for_voice_line', 'VoiceLineListCoordinator(', 'Account selected')
    choose = a.f('ChooseVoiceLineScreen')
    selected = a.f('SelectedVoiceLineDetailsScreen')
    contact = a.f('ContactScreen', 'sections/common')
    numbers = a.f('NumberSelectionForVoiceLineScreen')
    check = a.f('CheckoutScreen', 'sections/common')
    view = a.f('ViewVoiceLineScreen')
    unassigned = a.f('ViewVoiceLineUnAssignedScreen')
    assign = a.f('AssignVoiceLineScreen')
    adduser = a.f('AddNewUserManagementScreenView')
    added = a.f('AddEmployeeSuccessScreen', 'voice_line')
    a.edge(listing, choose, voice + 'manage_voice_line/voice_line_list', 'ChooseVoiceLineCoordinator(', 'Buy voice line')
    a.edge(choose, selected, voice + 'buy_voice_line/choose_voice_line', 'SelectedVoiceLineDetailsCoordinator(', 'Choose plan')
    a.edge(selected, contact, voice + 'buy_voice_line/selected_voice_line_details', 'ContactCoordinator(', 'Add contact details', 'Contact information required')
    a.edge(selected, numbers, voice + 'buy_voice_line/selected_voice_line_details', 'NumberSelectionForVoiceLineCoordinator(', 'Select numbers', 'Existing contact details sufficient')
    a.edge(contact, numbers, voice + 'buy_voice_line/selected_voice_line_details', 'NumberSelectionForVoiceLineCoordinator(', 'Continue after contact', 'Contact callback succeeds')
    a.edge(numbers, check, voice + 'buy_voice_line/number_selection_for_voice_line', 'CheckoutCoordinator(', 'Checkout selected voice numbers', 'Number reservation succeeds')
    for node, cond, needle in [(view, 'Voice line has assigned user', 'ViewVoiceLineScreen('), (unassigned, 'Voice line is unassigned', 'ViewVoiceLineUnAssignedScreen(')]:
        b.edge(listing, node, 'View selected voice line', [a.ev(voice + 'manage_voice_line/voice_line_list', 'ViewVoiceLineCoordinator('), a.ev(voice + 'common/view_voice_line/coordinator', needle)], condition=cond)
        a.edge(node, assign, voice + 'common/view_voice_line/coordinator', 'AssignVoiceLineCoordinator(', 'Assign / reassign employee')
    management = a.entry(a.f('UserManagementView', 'manage/user_management'))
    a.edge(management, adduser, sect + 'manage/user_management', 'AddNewUserManagementScreenCoordinator(', 'Add new employee', 'User-management add action')
    a.edge(adduser, added, voice + 'add_new_user_management_screen', 'AddEmployeeSuccessScreen(', 'Employee created', 'Employee-add response succeeds')
    b.note('Voice-line delete/unassign confirmations remain local sheets; assignment/API failure retains the source page. Static-content fetch failure does not create a voice-line landing screen.')

    _support(b, a, sect, support, menu, android, ah, ilink)
    _complaints(b, a, support, menu)
    _orders(b, a, sect, orders, android, ah, ilink)
    _notifications(b, a, sect, android, ah, ilink)
    _deeplinks(b, a, sect, android, ah, ilink)


def _support(b, a, sect, support, menu, android, ah, ilink):
    b.journey('support', 'Support, troubleshooting, help and chat', 'Support',
              'Backend support menus, login type and platform determine the destination.')
    landing = a.entry(a.f('SupportMenuScreen', 'bss/support_menu'))
    trouble = a.f('EndUserSupportScreen')
    not_supported = a.f('NotSupportedMemberScreen')
    number = a.f('EnterAccountNoModalSheetWrapper', kind='sheet')
    a.edge(landing, trouble, menu, 'EndUserSupportCoordinator(', 'End-user troubleshooting', 'menuId == 4034 && isEndUser')
    a.edge(trouble, number, support + 'end_user_troubleshoot/end_user/coordinator', 'EnterAccountNoModalSheetWrapper(', 'Enter account number', 'DisplayEnterAccountNoBottomSheetState')
    a.edge(trouble, not_supported, support + 'end_user_troubleshoot/end_user/coordinator', 'NotSupportedMemberCoordinator(', 'Member not supported', "response.apiErrorCode == 'support_error_0002'")
    result_ev = a.ev(support + 'end_user_troubleshoot/end_user/coordinator', "response.apiErrorCode == '123'")
    result = b.special('result', 'Troubleshooting result / restriction', 'terminal', [result_ev],
                       notes='Inline Flutter BaseScreen/GenericErrorWidget scaffolds for API errors, not separately named screens. Success continues to native instructions.')
    b.edge(trouble, result, 'Conditional API result', [result_ev], condition="Error 123 or other support eligibility/result branch")
    dispatch_ev = a.ev(menu, 'ChannelController.onSupportSelected(')
    dispatch = b.decision('menu', 'Native support menu action', 'Other support menu IDs; exceptions are Flutter troubleshooting and migrated track-order', [dispatch_ev])
    b.edge(landing, dispatch, 'Select support / quick-link item', [dispatch_ev], condition='Backend menu includes item; Flutter special handlers did not return')
    native_help = b.a('HelpAndSupportCenterActivity')
    native_accounts = b.a('ChooseAccountNumberActivity')
    chat = b.a('ChatInitiationAcitivity')
    store = b.a('StoreLocatorActivity')
    terms = b.a('GeneralTermsAndConditionsActivity')
    for target, needle, label, cond in [
        (native_help, 'HelpAndSupportCenterActivity::class.java', 'Android help centre', 'SUPPORT / SUPPORT_CENTRE_MENU'),
        (native_accounts, 'ChooseAccountNumberActivity::class.java', 'Android technical support', 'TECHNICAL_SUPPORT / SUPPORT_REQUEST_MENU'),
        (chat, 'ChatInitiationAcitivity::class.java', 'Android chat', 'CHAT / CHAT_SUB_MENU'),
        (store, 'StoreLocatorActivity::class.java', 'Android store locator', 'STORE_LOCATOR'),
        (terms, 'GeneralTermsAndConditionsActivity::class.java', 'Android terms / device care', 'TERMS_AND_CONDITIONS / DEVICE_CARE')]:
        a.edge(dispatch, target, ah, needle, label, cond, repo='A')
    category = b.a('HelpAndSupportCenterCategoriesActivity')
    video = b.a('YoutubePlayerActivity')
    chatbot = b.a('ChatBotWebViewActivity')
    webchat = b.a('WebChatlActivity')
    advanced = b.a('SupportAdvancedActivity')
    detail = b.a('StoreDetailsActivity')
    web = b.a('NewWebPageActivity')
    instructions = b.a('RequestSupportInfoActivity')
    a.edge(native_help, category, android + 'helpandsupport/HelpAndSupportCenterActivity.kt', 'HelpAndSupportCenterCategoriesActivity::class.java', 'Select help category / FAQ', repo='A')
    a.edge(category, video, android + 'helpandsupport/HelpAndSupportCenterCategoriesActivity.kt', 'YoutubePlayerActivity::class.java', 'Watch support video', 'Selected help item has video', repo='A')
    a.edge(native_help, chatbot, android + 'helpandsupport/HelpAndSupportCenterActivity.kt', 'ChatBotWebViewActivity::class.java', 'Open chatbot', 'Chat available and selected', repo='A')
    a.edge(chat, webchat, android + 'chat/ChatInitiationAcitivity.java', 'WebChatlActivity.class', 'Start chat session', 'Chat initialization succeeds', repo='A')
    a.edge(chat, advanced, android + 'chat/ChatInitiationAcitivity.java', 'SupportAdvancedActivity.class', 'Advanced support account selection', 'User chooses advanced support', repo='A')
    a.edge(store, detail, android + 'store_locator/StoreLocatorActivity.java', 'StoreDetailsActivity.start(', 'Selected store details', repo='A')
    a.edge(native_accounts, web, android + 'helpandsupport/ChooseAccountNumberActivity.kt', 'NewWebPageActivity::class.java', 'Motive consumer URL', 'Consumer URL supplied', repo='A')
    a.edge(native_accounts, instructions, android + 'helpandsupport/ChooseAccountNumberActivity.kt', 'RequestSupportInfoActivity::class.java', 'Support instructions', 'No consumer URL; API provides description', repo='A')
    for target, cond, needle in [(web, 'Support success includes consumer URL', 'NewWebPageActivity::class.java'), (instructions, 'Support success without consumer URL', 'RequestSupportInfoActivity::class.java')]:
        b.edge(trouble, target, 'Android final support instructions',
               [a.ev(support + 'end_user_troubleshoot/end_user/coordinator', 'ChannelController.navigateToSelfSupport('), a.ev(ah, needle, 'A')], condition=cond)
    ioshelp = b.i('HelpAndSupportCentreVC', 'SwiftSections/SwiftSections')
    iosaccounts = b.i('ChooseAccountVC')
    iosstore = b.i('StoreLocatorViewController', '.h')
    iosinstructions = b.i('SupportInstructionsVC')
    iosweb = b.i('CustomWebViewController', '.h')
    leaf = ilink + 'FlutterLinkable+SupportMenuActions.swift'
    common = 'SMB/SMB/BaseClasses/CommonMethods.m'
    for target, needle, label, cond in [
        (ioshelp, 'ShowHelpAndSupportVC(', 'iOS help centre', 'supportCentre; linked account and native dependency present'),
        (iosaccounts, 'showTechnicalSupportVC(', 'iOS technical-support account selection', 'technicalSupport; native dependency present'),
        (iosstore, 'getStoreLocatorVC(', 'iOS store locator', 'storeLocator; linked account and vendor available')]:
        a.edge(dispatch, target, leaf, needle, label, cond, repo='I')
    noop = b.unresolved('ios-request-noop', 'iOS support-request action: no screen', [a.ev(leaf, 'process no-op', 'I')], notes='Intentional parity with legacy SupportFt no-op. Android opens account selection for this menu.')
    b.edge(dispatch, noop, 'iOS Support Request', [a.ev(leaf, 'process no-op', 'I')], condition='supportRequest')
    ih = 'SwiftSections/SwiftSections/Sections/Help&SupportCentre/'
    ic = 'SwiftSections/SwiftSections/Sections/SupportCentre/'
    ioscategory = b.i('HelpCategoryDetailVC', 'SwiftSections/SwiftSections')
    iostechnical = b.i('TechnicalSupportVC')
    a.edge(ioshelp, ioscategory, ih, 'HelpCategoryDetailCoordinator(', 'Select category / FAQ', repo='I')
    a.edge(ioshelp, iostechnical, ih, 'TechnicalSupportCoordinator(', 'Request technical support', repo='I')
    a.edge(ioscategory, iosweb, ih + 'HelpCategoryDetail/Coordinator', 'CustomWebViewCoordinator(', 'Help video / web instructions', repo='I')
    a.edge(iosaccounts, iosinstructions, ic + 'ChooseAccount/Coordinator', 'SupportInstructionsCoordinator(', 'Support description', 'No Motive consumer URL', repo='I')
    a.edge(iosaccounts, iosweb, ic + 'ChooseAccount/Coordinator', 'CustomWebViewCoordinator(', 'Motive consumer web support', 'Consumer URL supplied', repo='I')
    a.edge(trouble, iosweb, ilink + 'FlutterLinkable+Support.swift', 'CustomWebViewCoordinator(', 'iOS final web instructions', 'motiveConsumerUrl and required request fields present', repo='I')
    a.edge(trouble, iosinstructions, ilink + 'FlutterLinkable+Support.swift', 'vendor.navigateToSupportInstructions(', 'iOS final instructions', 'Support description branch', repo='I')
    faq = b.service('faq-rate', 'External browser / app-rating service', [a.ev(ah, 'Const.URL_FAQ', 'A'), a.ev(leaf, 'SharedMethods.openUrl(', 'I')])
    b.edge(dispatch, faq, 'FAQ / rate application', [a.ev(ah, 'Const.URL_FAQ', 'A'), a.ev(leaf, 'showRateAppPopUpWithManuallyRating', 'I')], condition='FAQ / RATE_US menu', kind='service')
    for symbol, needle, cond in [('FeedbackVC', 'Constant.ViewControllers.feedback', 'feedBack'), ('TermsConditionsWebViewController', 'termsConditionsWebViewController', 'termsAndConditions'), ('DeviceCareViewController', 'deviceCareViewController', 'deviceCare')]:
        target = b.i(symbol, '.h')
        a.edge(dispatch, target, leaf, needle, 'iOS ' + cond, cond, repo='I')
    chatbot_source = 'SwiftSections/SwiftSections/Sections/ChatbotService/ChatbotManager/ChatbotManager.swift'
    b.edge(dispatch, iosweb, 'iOS chat web session', [a.ev(common, '[[ChatbotManager shared] getData]', 'I'), a.ev(chatbot_source, 'CustomWebViewCoordinator(', 'I')], condition='Chat action, logged profile/account and backend chatBotUrl available')
    store_details = b.i('StoreDetailsViewController', '.h')
    a.edge(iosstore, store_details, 'SMB/SMB/Sections/Store Locator/View Controllers/StoreLocatorViewController.m', 'instantiateViewControllerWithIdentifier:@"StoreDetailsViewController"', 'Selected store details', repo='I')
    b.note('Complaint menu 4035 on non-end-user opens Flutter complaint flow and still falls through to native onSupportSelected; this double dispatch is represented in the complaint graph.')
    b.note('Native launcher/login is excluded. Local widget composition and SDK/web content are not separate native screen steps.')


def _complaints(b, a, support, menu):
    b.journey('complaints', 'Raise a complaint', 'Support', 'Business complaint workflow; request type and API outcomes select the conditional steps.')
    landing = a.entry(a.f('SupportMenuScreen', 'bss/support_menu'))
    selected = a.f('SelectComplaintTypeScreen')
    subtype = a.f('SelectComplaintSubTypeScreen')
    party = a.f('SelectPartyAndAccountScreen')
    payment = a.f('PaymentComplaintScreen')
    requirements = a.f('ComplaintRequirementAndUploadScreen')
    review = a.f('ReviewComplaintRequestScreen')
    filter_sheet = a.f('AccountsFilterPopupScreen', kind='sheet')
    account_sheet = a.f('AccountBottomSheetScreen', kind='sheet')
    contact_sheet = a.f('AlternateContactBottomSheetScreen', kind='sheet')
    a.edge(landing, selected, menu, 'SelectComplaintTypeCoordinator(', 'Raise complaint', 'item.id == 4035 && !isEndUser')
    complaint = support + 'complaint/'
    a.edge(selected, subtype, complaint + 'select_complaint_type/coordinator', 'SelectComplaintSubTypeCoordinator(', 'Complaint type selected')
    a.edge(subtype, party, complaint + 'select_complaint_sub_type/coordinator', 'SelectPartyAndAccountCoordinator(', 'Select affected company/accounts', 'Subtype selection / company context resolves')
    a.edge(party, filter_sheet, complaint + 'select_party_and_account/coordinator', 'AccountFilterPopupCoordinator(', 'Filter affected accounts')
    a.edge(party, payment, complaint + 'select_party_and_account/coordinator', 'PaymentComplaintCoordinator(', 'Payment complaint details', 'Selected complaint subtype requires payment evidence')
    a.edge(party, requirements, complaint + 'select_party_and_account/coordinator', 'ComplaintRequirementAndUploadCoordinator(', 'Complaint requirements', 'Non-payment complaint branch')
    a.edge(payment, requirements, complaint + 'payment_complaint/coordinator', 'ComplaintRequirementAndUploadCoordinator(', 'Continue with payment evidence')
    a.edge(requirements, account_sheet, complaint + 'complaint_requirement_and_upload', 'AccountsBottomSheetCoordinator(', 'Select account rows', 'Linked-party account selection action')
    a.edge(requirements, review, complaint + 'complaint_requirement_and_upload/coordinator', 'ReviewComplaintRequestCoordinator(', 'Review complaint')
    a.edge(review, contact_sheet, complaint + 'review_complaint_request/coordinator', 'AlternateContactBottomSheetCoordinator(', 'Alternate contact')
    ev_result = a.ev(complaint + 'review_complaint_request/coordinator', '_navigateToStatusScreen(')
    success = b.special('success', 'Complaint submitted — Flutter success', 'terminal', [ev_result])
    b.edge(review, success, 'Submit complaint', [ev_result], condition='Submission response succeeds')
    a.edge(success, landing, complaint + 'review_complaint_request/coordinator', 'SupportMenuScreen(', 'Return to Flutter Support', 'isComingFromFlutter', kind='return')
    close = b.service('close-host', 'Close Flutter and return to native host', [a.ev(complaint + 'review_complaint_request/coordinator', 'ChannelController.closeFlutterApp(')])
    b.edge(success, close, 'Finish native-origin complaint', [a.ev(complaint + 'review_complaint_request/coordinator', 'ChannelController.closeFlutterApp(')], condition='!isComingFromFlutter', kind='return')
    native = b.unresolved('double-dispatch', 'Also dispatches native support menu', [a.ev(menu, '_moveToComplaint(context);'), a.ev(menu, 'ChannelController.onSupportSelected(')], notes='The 4035 branch does not return. Native destination depends platform menu handler; this is a recorded source behavior, not a recommended redesign.')
    b.edge(landing, native, 'Complaint tap also falls through', [a.ev(menu, '_handleMenuItemClick(')], condition='item.id == 4035 && !isEndUser', notes='Same tap initiates the Flutter complaint and native dispatch.')
    picker = b.service('files', 'File / camera attachment service', [a.ev(complaint + 'complaint_requirement_and_upload', 'ChannelController.openFilePicker(')])
    b.edge(requirements, picker, 'Attach required evidence', [a.ev(complaint + 'complaint_requirement_and_upload', 'ChannelController.openFilePicker(')], kind='service')
    b.note('Upload requirements, alternate contacts, account filters and payment evidence are conditional, not required for every complaint.')


def _orders(b, a, sect, orders, android, ah, ilink):
    b.journey('orders', 'Track orders, appointments and support tickets', 'Orders',
              'Migrated portal, current Flutter order list and configured native tracking remain separate routes.')
    support_menu = a.entry(a.f('SupportMenuScreen', 'bss/support_menu'))
    track = a.f('TrackOrderScreen', 'bss/track_order')
    listing = a.entry(a.f('OrdersListingScreen'))
    details = a.f('OrderDetailsScreen', 'tracking_order')
    slot = a.f('BookNewSlotWidget', kind='sheet')
    contact = a.f('UpdateSiteContactScreen')
    reasons = a.f('ReasonsScreen', 'tracking_order')
    cancel = a.f('CancellationInProgressScreen')
    a.edge(support_menu, track, sect + 'bss/support_menu/views/widgets/support_menu_success_widget.dart', 'TrackOrderScreen(', 'Migrated order portal', 'menuId == 4 && openLegacyTrackOrderScreen')
    a.edge(listing, details, orders + 'orders_listing', 'OrderDetailsCoordinator(', 'Selected order details')
    a.edge(details, slot, orders + 'order_details', 'RescheduleOrderCoordinator(', 'Reschedule appointment', 'Order permits reschedule; existing and new available slots loaded')
    a.edge(details, contact, orders + 'order_details', 'UpdateSiteContactScreen(', 'Update site contact', 'Order permits contact update')
    a.edge(details, reasons, orders + 'order_details', 'CancelOrderCoordinator(', 'Cancel order', 'Order cancellation permitted')
    a.edge(reasons, cancel, orders + 'cancel_order/coordinator', 'CancellationInProgressScreen(', 'Cancellation submitted', 'Cancel API succeeds')
    a.edge(cancel, listing, orders + 'cancel_order/coordinator', 'OrdersListingCoordinator(', 'Return to orders', kind='return')
    dashboard = a.entry(a.f('TrackOrderAndSupportSliderWidget', kind='content'))
    tickets = a.f('SupportTrackingTicketsScreen')
    ticket = a.f('SupportTrackingTicketsDetailScreen')
    a.edge(dashboard, tickets, sect + 'dashboard/common/views/widgets/track_order_and_support_slider.dart', 'SupportTrackingTicketsCoordinator(', 'Support tickets', 'Dashboard supports ticket tracking')
    a.edge(tickets, ticket, sect + 'dashboard/support_tracking', 'SupportTrackingTicketsDetailsCoordinator(', 'Selected ticket details')
    native = b.a('OrderTrackingActivity')
    ndetails = b.a('OrderDetailsActivity', 'orders_tracking/details')
    fleet_sheet = b.a('DeliveryTrackingDialogFragment', kind='sheet')
    fleet = b.a('FleetTrackOrderDetailsActivity')
    ev = a.ev(ah, 'fun openNativeOrderTracking', 'A')
    native_entry = b.decision('legacy', 'Configured native order tracking', 'Non-migrated notification and legacy dashboard enabled; or native support menu track-order fallback', [ev], default='Legacy Dashboard false: notification uses Flutter orders')
    b.entry(native_entry)
    a.edge(native_entry, native, ah, 'OrderTrackingActivity::class.java', 'Android native orders', repo='A')
    a.edge(native, ndetails, android + 'orders_tracking/main/fragments', 'OrderDetailsActivity.class', 'Open order / history details', repo='A')
    a.edge(ndetails, fleet_sheet, android + 'orders_tracking/details/OrderDetailsActivity.java', 'DeliveryTrackingDialogFragment.Companion.newInstance', 'Track shipment', 'Fleet order tracking available', repo='A')
    a.edge(fleet_sheet, fleet, android + 'orders_tracking/fleet_tracking/DeliveryTrackingDialogFragment.kt', 'FleetTrackOrderDetailsActivity::class.java', 'Shipment details', repo='A')
    ios = b.i('OrdersListViewController', '.h')
    ifleet = b.i('FleetOrderDetailsViewController')
    itrack = b.i('FleetOrderTrackingViewController')
    a.edge(native_entry, ios, ilink + 'FlutterLinkable+Deeplink.swift', 'Constant.ViewControllers.ordersListVC', 'iOS native orders', repo='I')
    a.edge(ios, ifleet, 'SMB/SMB/Sections/Track Order/View Controllers/Custom Cells/ViewOrderDetailsCell.m', 'FleetOrderDetailsWrapper', 'Selected native order', repo='I')
    a.edge(ifleet, itrack, 'SwiftSections/SwiftSections/Sections/OrderManagement/OrderDetails/Coordinator', 'FleetOrderTrackingCoordinator(', 'Track fleet order', 'Order has tracking information', repo='I')
    web = b.service('portal', 'BSS tracking web content', [a.ev(sect + 'bss/track_order/track_order_screen.dart', 'BSSConstants.trackOrderUrl')])
    b.edge(track, web, 'Render authenticated portal', [a.ev(sect + 'bss/track_order/track_order_screen.dart', 'BSSConstants.trackOrderUrl')], kind='service')
    b.note('Appointment selection is a Flutter bottom sheet; reschedule success uses inline SuccessCoordinator content. Orders API permissions govern contact/cancel/reschedule buttons. TrackOrderScreen is Flutter despite legacy input naming.')
    b.note('Android openNativeOrderTracking is implemented in current source. Older docs claiming the Android handler is absent are stale. Old iOS OrderDetailViewController caller is commented out; the active row launches FleetOrderDetailsViewController.')


def _notifications(b, a, sect, android, ah, ilink):
    b.journey('notifications', 'Notifications and in-app campaign actions', 'Notifications',
              'Bell/history and screen campaign popup converge on Flutter detail and typed action routing.')
    count = a.entry(a.f('NotificationCountWidget', kind='content'))
    listing = a.f('NotificationsListingView')
    detail = a.f('NotificationDetailsView')
    popup = a.entry(a.f('ScreenNotificationDialog', kind='sheet'))
    a.edge(count, listing, sect + 'notifications/notification_count', 'AppRoutes.notificationsListing', 'Open notification history')
    a.edge(listing, detail, sect + 'notifications/notifications_listing', 'AppRoutes.notificationDetails', 'Select notification')
    a.edge(popup, detail, sect + 'notifications/screen_notification/views/screen_notification_host.dart', 'NotificationDetailsCoordinator(', 'Read campaign details', 'Campaign action opens detail')
    ev = a.ev(sect + 'notifications/notification_details/viewmodel', 'DeeplinkService.process(')
    route = b.decision('action', 'Notification action type and account context', 'Typed notification handler + payload + role/account/session', [ev])
    b.edge(detail, route, 'Tap notification action', [ev])
    routers = 'lib/core/deeplink_manager/routers/notification/'
    for symbol, hint, scope, needle, label, condition in [
        ('TrackOrderScreen', 'bss/track_order', 'support_notification_router.dart', 'TrackOrderScreen(', 'BSS tracking portal', 'SessionProvider.isMigrated'),
        ('OrdersListingScreen', 'tracking_order', 'support_notification_router.dart', 'OrdersListingCoordinator(', 'Current Flutter orders', '!isMigrated && !isLegacyDashboardEnabled'),
        ('PrepaidHomeScreen', '', 'pay_notification_router.dart', 'PrepaidHomeScreen(', 'Prepaid home', 'Prepaid action eligibility/account context'),
        ('MobilePlanListScreen', '', 'shop_notification_router.dart', 'MobilePlanListCoordinator(', 'Mobile plans', 'Mobile-plan notification handler selects Flutter list'),
        ('AddonsListView', '', 'shop_notification_router.dart', 'AddonsListCoordinator(', 'Add-ons / roaming', 'Revamped add-on notification branch'),
        ('CompaniesScreen', 'bss/track_order', 'onboarding_notification_router.dart', 'CompaniesScreen(', 'Company registration tracking', 'Onboarding handler selects Flutter companies'),
    ]:
        target = a.f(symbol, hint)
        a.edge(route, target, routers + scope, needle, label, condition)
    native_ev = a.ev(routers, 'ChannelController.openSelectedNotification(')
    native = b.decision('native-actions', 'Native notification action dispatcher', 'Other notification linkAction values; platform implementation and payload choose action', [native_ev])
    b.edge(route, native, 'Native fallback/action', [native_ev], condition='Handler delegates to openSelectedNotification')
    legacy_ev = a.ev('lib/core/deeplink_manager/handlers/notification/support_notification_handlers.dart', 'await router.openNativeOrderTrackingDetail(')
    legacy = b.portal('legacy-orders', 'Configured native tracking', 'orders', [legacy_ev])
    b.edge(route, legacy, 'Native order tracking fallback', [legacy_ev], condition='!isMigrated && isLegacyDashboardEnabled', default='false')
    esim = b.unresolved('esim', 'eSIM notification: no destination', [a.ev(routers + 'manage_notification_router.dart', 'Future<void> openEsim')], notes='Current openEsim is TODO/no-op; SIM replacement/eSIM flows elsewhere are separately reachable.')
    b.edge(route, esim, 'eSIM action', [a.ev(routers + 'manage_notification_router.dart', 'Future<void> openEsim')], condition='eSIM notification action')
    # Current Android bridge bypasses old notification detail Activities and calls
    # actual action methods. Resolve explicit native screen targets in those methods.
    native_text = b.text('A', ah)
    body_start = native_text.index('    fun redirectUserToRespectiveFlow(')
    body_end = native_text.find('\n    fun ', body_start + 10)
    action_body = native_text[body_start:body_end if body_end >= 0 else len(native_text)]
    calls = list(dict.fromkeys(re.findall(r'\b((?:moveTo|navigateTo|open)[A-Z]\w*)\(', action_body)))
    targets = {}
    for method in calls:
        match = re.search(r'\n    (?:private )?fun ' + re.escape(method) + r'\(', native_text)
        if not match:
            continue
        end = native_text.find('\n    ', match.end())
        next_method = re.search(r'\n    (?:private )?fun ', native_text[match.end():])
        method_text = native_text[match.start():match.end() + next_method.start() if next_method else len(native_text)]
        active_method_text = re.sub(r'/\*.*?\*/', '', method_text, flags=re.S)
        active_method_text = '\n'.join(line for line in active_method_text.splitlines() if not line.strip().startswith('//'))
        for symbol in re.findall(r'\b(\w+Activity)::class\.java', active_method_text):
            targets.setdefault(symbol, method)
    for symbol, method in targets.items():
        target = b.a(symbol)
        # Evidence at dispatcher call plus callee's actual Activity destination.
        call_line = next(line.strip() for line in action_body.splitlines() if method + '(' in line and not line.strip().startswith('//'))
        call_ev = b.ev('A', ah, call_line)
        target_ev = a.ev(ah, symbol + '::class.java', 'A')
        b.edge(native, target, re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', method), [call_ev, target_ev],
               condition='linkAction selects ' + method + '; account/backend prerequisites apply')
    ios_bridge = a.ev(ilink + 'FlutterLinkable+Deeplink.swift', 'DeepLinkManager.shared.handleNotificationDeepLink(', 'I')
    ios_portal = b.portal('ios-actions', 'iOS notification destinations', 'notification-ios', [ios_bridge])
    b.edge(native, ios_portal, 'iOS payload-driven native action', [ios_bridge], condition='iOS native fallback')
    b.note('Old Android NotificationActionController detail-Activity inventory is not a root: current openSelectedNotification calls redirectUserToRespectiveFlow directly. Dart openNotificationList has no active producer; do not promote its registry or legacy native history to Flutter-login reachability.')
    b.note('In-app campaign visibility is fetched per current screen/login type. A missing or ineligible campaign yields no popup; its absence is not a navigation failure.')

    _ios_notification_destinations(b, a, ilink)


def _deeplinks(b, a, sect, android, ah, ilink):
    b.journey('url-deeplinks', 'URL links and deferred alternate entries', 'Notifications',
              'Alternate entry routes are attached to the same business screens; authentication/config/payload checks remain explicit.')
    service_ev = a.ev('lib/core/deeplink_manager/core/deeplink_service.dart', 'static void setUrl(')
    intake = b.service('url', 'App URL / content-link intake', [service_ev])
    b.entry(intake)
    manager_ev = a.ev('lib/core/deeplink_manager/core/manager/deeplink_manager_v2.dart', 'processPendingDeeplink')
    route = b.decision('resolve', 'Resolve link and session eligibility', 'URL type + session authorization + role/account/profile menus + runtime parameters', [manager_ev])
    b.edge(intake, route, 'Process or defer URL', [service_ev, manager_ev], kind='service')
    routers = 'lib/core/deeplink_manager/routers/url/'
    login = a.f('MainLoginScreen')
    a.edge(route, login, routers + 'onboarding_deeplink_router.dart', 'LoginCoordinator(', 'Authentication required', 'Owner authorization/onboarding link requires login')
    track = a.f('TrackOrderScreen', 'bss/track_order')
    a.edge(route, track, routers + 'support_deeplink_router.dart', 'TrackOrderScreen(', 'Migrated order management', 'Session is migrated')
    addons = a.f('AddonsListView')
    a.edge(route, addons, routers + 'shop_deeplink_router.dart', 'AddonsListCoordinator(', 'Add-on shop URL', 'Handler selects revamped add-on list')
    internet = a.f('ShopScreen', 'internet_bundle_plan_selection')
    a.edge(route, internet, routers + 'shop_deeplink_router.dart', 'InternerBundlePlanCoordinator(', 'Internet bundle URL', 'Payload / session qualifies for Flutter internet bundle')
    device = a.f('DeviceAssuredBuyBackScreen')
    a.edge(route, device, routers + 'shop_deeplink_router.dart', 'DeviceAssuredBuyBackScreen(', 'Device assured buyback', 'Buyback eligibility handler')
    unauthorized = a.f('UnauthorizedUserView')
    a.edge(route, unauthorized, routers + 'shop_deeplink_router.dart', 'UnauthorizedUserCoordinator(', 'Unauthorized purchase', 'Handler rejects current user/account authorization')
    legacy_ev = a.ev(routers, 'ChannelController.openUrlDeeplinkFlow(')
    native = b.decision('native', 'Native URL dispatcher', 'Other selected URL types and payload; login is already Flutter in this inventory', [legacy_ev])
    b.edge(route, native, 'Delegate URL action', [legacy_ev], condition='Current Dart router calls openUrlDeeplinkFlow')
    dh = android + 'splash/DeeplinkHolder.kt'
    source = b.text('A', dh)
    targets = []
    active_source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
    for line in active_source.splitlines():
        if line.strip().startswith('//'):
            continue
        for symbol in re.findall(r'\b(\w+Activity)::class\.java', line):
            if symbol not in targets and symbol not in ('LoginActivity', 'IndividualLoginActivity', 'OverviewBottomNavigationActivity', 'SMBFlutterActivity'):
                targets.append(symbol)
    for symbol in targets:
        target = b.a(symbol)
        ev = a.ev(dh, symbol + '::class.java', 'A')
        b.edge(native, target, 'Android URL-selected destination', [a.ev(ah, 'DeeplinkHolder.openUrlDeeplinkFlow', 'A'), ev],
               condition='DeeplinkHolder URL/action match selects ' + symbol,
               notes='See source condition and payload checks at the destination branch; not every URL/user reaches this destination.')
    ios_ev = a.ev(ilink + 'FlutterLinkable+Deeplink.swift', 'DeepLinkManager.shared.processDeeplink()', 'I')
    ios = b.unresolved('ios-native-url', 'iOS native URL mapper / registered routers', [ios_ev],
                       notes='DeepLinkManager uses URL template/type registration and runtime route vendors. Business screen destinations mapped in their owning journey; unknown vendor output remains unresolved rather than fabricated.')
    b.edge(native, ios, 'iOS URL dispatch', [ios_ev], condition='Valid nonempty URL and registered URL type')
    b.note('Non-migrated order-management URL currently delegates to native and selects Support; OrdersListingCoordinator call is commented out. Notification order tracking instead uses Flutter Orders when the new dashboard is enabled.')
    b.note('Shop mobile-plan URL still delegates native (the Flutter list is commented out). Home/Shop/Manage link handlers also select existing tabs; they do not imply a new screen push.')
    b.note('Native login in legacy DeeeplinkHolder guards is obsolete for this diagram root and is excluded; Flutter MainLoginScreen handles active login. Cold-start/host plumbing is a service boundary, not a second login root.')


def _ios_notification_destinations(b, a, ilink):
    b.journey('notification-ios', 'iOS native notification destinations', 'Notifications',
              'Current native DeepLinkManager action implementations; payload and eligibility choose each branch.')
    bridge = a.ev(ilink + 'FlutterLinkable+Deeplink.swift', 'DeepLinkManager.shared.handleNotificationDeepLink(', 'I')
    route = b.decision('action', 'iOS notification linkAction', 'Registered notification template and current payload', [bridge])
    b.entry(route)
    path = 'SMB/SMB/SwiftCodeBase/Core/Manager/DeepLinkManager/NotificationTypes/NotificationTypes.swift'
    constants = b.text('I', 'CoreSwift/CoreSwift/Source/Constants/Constant+StoryBoards.swift')
    values = dict(re.findall(r'public static let (\w+) = "(\w+)"', constants))
    text = b.text('I', path)
    b._index('I')
    owner = 'Notification action'
    seen = set()
    for line in text.splitlines():
        if line.strip().startswith('//'):
            continue
        match = re.search(r'\bclass (\w+)', line)
        if match:
            owner = match.group(1)
        candidates = re.findall(r'as\?\s+(\w+(?:VC|ViewController))\b', line)
        candidates += [values.get(key, '') for key in re.findall(r'Constant.ViewControllers\.(\w+)', line)]
        for symbol in candidates:
            if not symbol or symbol in seen or symbol in ('LoginViewController', 'LoginVC'):
                continue
            matches = b._classes['I'].get(symbol, [])
            if not matches:
                continue
            preferred = [p for p,l in matches if p.endswith('.h')] or [p for p,l in matches if p.startswith('SwiftSections/SwiftSections/')] or [p for p,l in matches]
            target = b.i(symbol, preferred[0])
            ev = b.ev('I', path, line.strip())
            label = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', owner.replace('NotificationDeepLink', '').replace('Notification', ''))
            b.edge(route, target, label or 'Native notification action', [bridge, ev],
                   condition=owner + ' template matches; native session/account/API checks pass')
            seen.add(symbol)
    for symbol, scope, needle, action in [
        ('LeadCaptureVC', 'SwiftSections/SwiftSections/Sections/LeadCapture', 'LeadCaptureVC', 'LeadCapture'),
        ('RegistrationStatusDetailsVC', 'SwiftSections/SwiftSections/Sections/Registration', 'RegistrationStatusDetailsVC', 'RegistrationStatus')]:
        matches = b._classes['I'].get(symbol, [])
        if not matches:
            continue
        # The registered notification source explicitly constructs these coordinators.
        coordinator = action + 'Coordinator('
        if coordinator not in text:
            continue
        preferred = [p for p,l in matches if p.startswith('SwiftSections/SwiftSections/')]
        target = b.i(symbol, (preferred or matches)[0][0] if isinstance((preferred or matches)[0], tuple) else (preferred or matches)[0])
        b.edge(route, target, action + ' action', [bridge, a.ev(path, coordinator, 'I')], condition='Template and action prerequisites match')
    b.note('URLs, app rating, vendor web content and Flutter wrapper callbacks are actions/services rather than additional fixed native screens. eSIM native notification action also has no completed destination in this legacy handler.')
