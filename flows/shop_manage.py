"""Source-backed Shop, internet-order and Manage journey diagrams.

Curated edges use executable constructor/dispatch references, rather than treating
imports or screen filenames as navigation. Shared implementation classes retain
one canonical identity even when used by several journeys.
"""
import re


def build(b):
    for repo in ('F', 'A', 'I'):
        b._index(repo)

    def evidence(repo, region, needle):
        matches = []
        for (r, path), content in sorted(b._text.items()):
            if r != repo or region not in path or path.endswith('.h'):
                continue
            for lineno, line in enumerate(content.splitlines(), 1):
                clean = line.strip()
                if needle in line and not clean.startswith(('import ', '#import', '//', '*', 'class ', '@interface', '@implementation')) and not re.match(r'(?:const\s+)?\w+\(\{', clean):
                    matches.append({'repo': repo, 'path': path, 'line': lineno, 'excerpt': line.strip()[:350]})
                    break
        if not matches:
            raise ValueError(f'No executable reference {repo} {region} {needle}')
        return matches[0]

    def node(repo, symbol, hint='', **kw):
        matches = [(p, l) for p, l in b._classes[repo].get(symbol, []) if hint in p]
        if len(matches) > 1:
            declarations = [(p, l) for p, l in matches if p.endswith('.h')]
            if len(declarations) == 1:
                hint = declarations[0][0]
        if symbol in ('AddressPopupScreen', 'MultiSimPopupScreen', 'UaePassBottomSheetView', 'ViewQrCodeBottomSheetView', 'AccountLimitBottomSheetVC'):
            kw.setdefault('kind', 'sheet')
        return b.screen(repo, symbol, hint, **kw)

    def start(key, title, family, symbol, hint='', description=''):
        b.journey(key, title, family, description or 'Availability depends on backend menus, account eligibility and the selected entry path.')
        n = node('F', symbol, hint)
        b.entry(n)
        return n

    def add(src, repo, symbol, hint, region, needle, label='Continue', condition='', kind='navigation'):
        n = node(repo, symbol, hint)
        b.edge(src, n, label, [evidence(repo, region, needle)], condition=condition, kind=kind)
        return n

    def f(src, symbol, hint, region, needle, label='Continue', condition='', kind='navigation'):
        return add(src, 'F', symbol, hint, region, needle, label, condition, kind)

    def decision(src, key, label, predicate, region, needle, default=None):
        ev = evidence('F', region, needle)
        n = b.decision(key, label, predicate, [ev], default=default)
        b.edge(src, n, 'Evaluate condition', [ev], kind='decision')
        return n

    def service(src, key, label, repo, region, needle, condition=''):
        ev = evidence(repo, region, needle)
        n = b.service(key, label, [ev])
        b.edge(src, n, label, [ev], condition=condition, kind='service')
        return n

    shop = start('shop-browse', 'Shop categories and account selectors', 'Shop', 'ShopHomeScreen', 'shop_home')
    cat = f(shop, 'ShopSubcategoryScreen', 'shop_subcategory', 'core/deeplink_manager', 'ShopSubcategoryCoordinator(', 'Category selected', 'Backend category requires submenu')
    prod = f(shop, 'SelectProductScreen', 'shop/select_product', 'shop_menu_navigation_helper.dart', 'SelectProductCoordinator(', 'Menu or banner selected', 'Menu-link category')
    party = f(prod, 'SelectPartyIdScreen', 'shop/select_party_id', 'shop/select_product', 'SelectPartyIdCoordinator(', 'Select company', 'Menu account-selection flags require company')
    acc = f(party, 'SelectAccountScreen', 'shop/select_account', 'shop/select_party_id', 'SelectAccountCoordinator(', 'Select accounts', 'Account selection required')
    f(acc, 'UploadFileScreen', 'shop/shop_file_upload', 'shop/select_account', 'UploadFileCoordinator(', 'Bulk account upload', 'Bulk-upload action selected')
    b.note('Backend MenuLink showMenu, hasCard, selectAccount, multiSelection and account-selection response control selector steps; selectors are not universally mandatory.')

    shop = start('shop-recommendations', 'Shop and individual recommended offers / Careem', 'Shop', 'ShopHomeScreen', 'shop_home')
    d = decision(shop, 'offer', 'Careem offer?', 'offer.isCareemOffer', 'shop_menu_navigation_helper.dart', 'if (offer.isCareemOffer)')
    careem = f(d, 'CareemPromoScreen', 'careem_promo', 'careem_promo/coordinator', 'CareemPromoScreen(', 'Careem offer', 'isCareemOffer = true')
    f(careem, 'TermsAndConditionScreenCareemPlus', 'careem', 'careem_promo', 'TermsAndCondition', 'Read terms', 'Terms action selected')
    native = add(careem, 'A', 'CareemSubscriptionWebViewActivity', '', 'flutter/FlutterNavigationHandler', 'CareemSubscriptionWebViewActivity', 'Purchase subscription', 'Selected account is eligible')
    b.edge(native, careem, 'Return / refresh offer status', [evidence('F', 'careem_promo', 'navigateToCareemPlusWebview')], kind='return')
    add(d, 'A', 'ShopRecommendationActivity', '', 'flutter/FlutterNavigationHandler', 'ShopRecommendationActivity', 'Recommended offer', 'Not Careem; QUICK_ACCESS')
    add(d, 'A', 'RecommendationActivity', '', 'flutter/FlutterNavigationHandler', 'RecommendationActivity', 'Recommended offer', 'Not Careem; other login types')
    add(d, 'I', 'RecommendedPlansDetailVC', '', 'ShopRecommendedOffersRouter', 'getRecommended', 'Recommended offer (iOS)', 'Not Careem')
    add(shop, 'A', 'ShopInventoryActivity', '', 'flutter/FlutterNavigationHandler', 'ShopInventoryActivity', 'View all offers')
    add(shop, 'I', 'ShopPackagesListViewController', '', 'FlutterLinkable+Shop', 'PackageTypeRecommendedPEGA', 'View all offers (iOS)')

    home = start('shop-mobile-purchase', 'Mobile plan purchase, quantities and delivery', 'Shop', 'MobilePlanListScreen', 'shop/plans/mobile_plan_list/')
    detail = f(home, 'MobilePlanListDetailView', 'mobile_plan_list_detail', 'shop/plans/mobile_plan_list/', 'MobilePlanListDetailCoordinator(', 'Select plan')
    numbers = f(detail, 'MobilePlanNumberListView', 'mobile_plan_number_list', 'shop/plans/mobile_plan_list_detail', 'MobilePlanNumberListCoordinator(', 'Choose numbers', 'Normal order quantity and eligibility')
    selection = f(numbers, 'MobilePlanListNumberSelectionScreen', 'mobile_plan_list_number_selection', 'shop/plans/mobile_plan_number_list', 'MobilePlanListNumberSelectionCoordinator(', 'Select preferred number')
    lead = f(detail, 'MobilePlanListLeadCaptureView', 'mobile_plan_list_lead_capture', 'shop/plans/mobile_plan_list_detail', 'MobilePlanListLeadCaptureCoordinator(', 'Capture lead', 'Quantity/plan requires lead capture')
    f(detail, 'MobilePlanListDetailUploadView', 'mobile_plan_list_detail_upload', 'shop/plans/mobile_plan_list_detail', 'MobilePlanListDetailUploadCoordinator(', 'Bulk documentation', 'Upload branch selected')
    delivery = f(numbers, 'SimDeliveryOptionsView', 'sim_delivery_options', 'shop/plans/mobile_plan_number_list', 'SimDeliveryOptionsCoordinator(', 'Choose SIM and delivery')
    b.edge(lead, delivery, 'Continue eligible order', [evidence('F', 'shop/plans/mobile_plan_list_lead_capture', 'SimDeliveryOptionsCoordinator(')])
    checkout = f(delivery, 'MobilePlanCheckoutView', 'mobile_plan_checkout', 'shop/plans/mobile_plan_checkout/coordinator', 'MobilePlanCheckoutView(', 'Review checkout')
    f(checkout, 'PhysicalCheckoutSuccessViewView', 'physical_checkout_success_view', 'shop/plans/mobile_plan_number_list', 'PhysicalCheckoutSuccessViewCoordinator(', 'Order complete', 'Physical SIM order')
    f(checkout, 'SimReplacementSuccessView', 'sim_replacement_success', 'shop/plans/mobile_plan_number_list', 'SimReplacementSuccessCoordinator(', 'Order complete', 'UAE Pass / eSIM branch')
    service(delivery, 'identity', 'UAE PASS / EFR identity capability', 'F', 'sim_delivery_options', 'UaePass', 'Identity verification required; see SIM identity journey')

    home = start('shop-addons', 'Buy addons and roaming packages', 'Shop', 'AddonsListView', 'addons_list_view.dart')
    d = decision(home, 'entry', 'Account already known?', 'QUICK_ACCESS or isAccountInquiryFLow; otherwise company/account selection', 'addons_revamp/addons_list', 'isAccountInquiryFLow')
    party = f(d, 'AddonPartySelectionView', 'addons_revamp/party_selection', 'addons_revamp/addons_list', 'AddonPartySelectionCoordinator(', 'Choose company', 'Admin Shop entry without selected inquiry account')
    acc = f(party, 'RevampAccountSelectionScreen', 'revamp_account_selection', 'addons_revamp/party_selection', 'RevampAccountSelectionCoordinator(', 'Choose accounts')
    review = f(acc, 'ReviewCheckoutView', 'addons_revamp/review_checkout', 'addons_revamp/revamp_account_selection', 'ReviewCheckoutCoordinator(', 'Review compatible accounts')
    b.edge(d, review, 'Review linked/inquiry account', [evidence('F', 'addons_revamp/addons_list', 'ReviewCheckoutCoordinator(')], condition='QUICK_ACCESS or explicit account inquiry')
    f(acc, 'PartialSuccessView', 'partial_success', 'addons_revamp/revamp_account_selection', 'PartialSuccessCoordinator(', 'Some accounts incompatible', 'Partial compatibility result')
    f(acc, 'ErrorReportScreen', 'error_report', 'addons_revamp', 'ErrorReportCoordinator(', 'View compatibility errors', 'Error report requested')
    f(home, 'UnauthorizedUserView', 'unauthorized_user', 'core/deeplink_manager/routers/url/shop_deeplink_router', 'UnauthorizedUserCoordinator(', 'Not authorized', 'Authorization/deep-link guard')
    pay = f(review, 'PaymentMethodsScreen', 'payments', 'addons_revamp/review_checkout', 'PaymentMethodsCoordinator(', 'Choose payment method', 'Payment required')
    service(pay, 'payment', 'Native wallet / gateway capability', 'F', 'payments', 'startPayment', 'Selected payment method needs platform gateway')
    f(review, 'SuccessFailureView', 'addons_revamp', 'addons_revamp/review_checkout', 'SuccessFailureView(', 'Submit result', 'Submission success/failure')
    f(pay, 'FlowResultScreen', 'flow_result', 'payments', 'FlowResultScreen(', 'Payment result')
    b.note('isRoamingAddon changes the shared catalogue mode; prepaid-home buy-addon entry is a separate native virtual-prepaid Shop journey. END_USER addon URL enters review directly; FULL_ACCESS/2 addon URL selects company/accounts.')

    home = start('internet-order', 'Internet bundle purchase and serviceability', 'Internet orders', 'ShopScreen', 'internet_bundle_plan_selection')
    d = decision(home, 'session', 'Signed in?', 'Existing linked companies versus guest authentication', 'internet_bundle_plan_details/coordinator', 'SelectPartyIdCoordinator(')
    party = f(d, 'SelectPartyIdScreen', 'lead_to_order/app_login_module/party_selection', 'internet_bundle_plan_details/coordinator', 'SelectPartyIdCoordinator(', 'Choose company', 'Signed-in / registration completed')
    login = f(d, 'AppLoginRegisterScreen', 'lead_to_order/app_login_module/login_or_register', 'internet_bundle_plan_details/coordinator', 'AppLoginRegisterCoordinator(', 'Login or register', 'Guest entry')
    f(login, 'AppLoginScreen', 'lead_to_order/app_login_module/login/', 'login_or_register', 'AppLoginCoordinator(', 'Login', 'Guest chooses login')
    loc = f(party, 'LocationSelectionScreen', 'lead_to_order/app_login_module/location_selection', 'party_selection', 'LocationSelectionCoordinator(', 'Choose location')
    f(loc, 'GoogleLocationScreen', 'google_location', 'location_selection', 'GoogleLocationCoordinator(', 'Map location', 'Map entry selected')
    f(loc, 'OtherLocationScreen', 'other_location', 'location_selection', 'OtherLocationCoordinator(', 'Other location', 'Alternate location selected')
    available = f(loc, 'SiteServiceableScreen', 'location_selection', 'location_selection', 'SiteServiceableCoordinator(', 'Check serviceability')
    num = f(available, 'NumberScreen', 'app_login_module/number/', 'location_selection', 'MainNumberCoordinator(', 'Choose main number', 'Serviceable location')
    checkout = f(num, 'L2oCheckoutScreen', 'l2o_checkout', 'app_login_module/number', 'L2oCheckoutCoordinator(', 'Review order')
    f(checkout, 'WhatsNextScreen', 'whats_next', 'l2o_checkout', 'WhastNextCoordinator(', 'Order submitted', 'Submit success')
    f(home, 'TermsAndConditionL2OScreen', 'lead_to_order/terms_and_condition', 'internet_bundle_plan_details', 'TermsAndConditionL2OCoordinator(', 'Read plan terms', 'Terms action selected')
    f(checkout, 'CheckoutTermsAndConditionL2OScreen', 'lead_to_order', 'l2o_checkout', 'CheckoutTermsAndConditionL2OCoordinator(', 'Read checkout terms')
    b.note('PlanDetailScreen is intentionally omitted: its visible constructors in PlanDetailsCoordinator are commented; the coordinator performs routing immediately.')

    home = start('fixed-porting', 'Switch fixed number to Etisalat', 'Internet orders', 'SwitchToEtisalatScreen', 'FNP')
    verify = f(home, 'VerifyFixedNumberScreen', 'verify_fixed_number', 'FNP', 'VerifyFixedNumberCoordinator(', 'Verify porting number')
    plans = f(verify, 'ShopScreen', 'internet_bundle_plan_selection', 'verify_fixed_number', 'PlansAsPerAccountsCoordinator(', 'Eligible internet plans', 'Number verification succeeds')
    main = f(plans, 'SelectMainNumberScreen', 'lead_to_order/FNP/select_main_number', 'location_selection', 'SelectMainNumberCoordinatorFNP(', 'Choose main number')
    num = f(main, 'NumberScreen', 'app_login_module/number/', 'FNP/select_main_number', 'MainNumberCoordinator(', 'Number details')
    app = f(num, 'ApplicationDetailsScreen', 'FNP/application_details', 'app_login_module/number', 'ApplicationDetailsCoordinator(', 'Porting application', 'FNP order variant')
    checkout = f(app, 'L2oCheckoutScreen', 'l2o_checkout', 'FNP/application_details', 'L2oCheckoutCoordinator(', 'Review order', 'Trade-license document is valid')
    f(checkout, 'WhatsNextScreen', 'whats_next', 'l2o_checkout', 'WhastNextCoordinator(', 'Order submitted', 'Submit success')
    b.note('Identity, company/account selection and location/serviceability steps reuse internet-order paths according to login and porting response; not every selector is compulsory.')

    home = start('saved-orders', 'Resume saved internet or porting order', 'Internet orders', 'LoadingScreenForResumeOrder', 'loading_screen_for_resume_order')
    for symbol, hint, needle, cond in [
        ('NumberScreen', 'app_login_module/number/', 'MainNumberCoordinator(', 'l20mainNumber or fnpMainNumber'),
        ('L2oCheckoutScreen', 'l2o_checkout', 'L2oCheckoutCoordinator(', 'l20Checkout or fnpCheckout'),
        ('ApplicationDetailsScreen', 'FNP/application_details', 'ApplicationDetailsCoordinator(', 'fnpApplicationDetails'),
        ('SelectMainNumberScreen', 'FNP/select_main_number', 'SelectMainNumberCoordinatorFNP(', 'fnpSelectedMainNumber')]:
        f(home, symbol, hint, 'loading_screen_for_resume_order', needle, 'Restore saved step', cond, 'navigation')

    home = start('contract-renewal', 'Renew contract', 'Shop', 'ReviewContractScreen', 'renew_plan/review_contract')
    device = f(home, 'SelectDeviceScreen', 'renew_plan/select_device', 'review_contract/coordinator', 'SelectDeviceCoordinator(', 'Select device', 'Renewal includes a device')
    checkout = f(home, 'CheckoutScreen', 'common/checkout', 'review_contract/coordinator', 'CheckoutCoordinator(', 'Review renewal')
    b.edge(device, checkout, 'Review selected device', [evidence('F', 'review_contract/coordinator', 'CheckoutCoordinator(')])
    b.note('Appointment slot change is an in-checkout interaction; ChangeSlotScreen is a static-content model, not a screen widget.')

    home = start('manage-selection', 'Manage products: company and account selection', 'Manage', 'AdminManageMenuScreen', 'admin_manage_menu')
    sub = f(home, 'MenuSubcategoryScreen', 'manage/menu_subcategory', 'admin_manage_menu', 'MenuSubcategoryCoordinator(', 'Select product service', 'Products/menu returned by backend')
    d = decision(sub, 'type', 'Which service?', 'menuLink.subMenuType', 'manage_menu_sub_category_navigator', 'switch (menuType)')
    party = f(d, 'SelectPartyIdScreen', 'manage/party_id_selection', 'manage_menu_sub_category_navigator', 'SelectPartyIdCoordinator(', 'Select company/account', 'Internet change plan, shift, remove subscription or SIM replacement')
    for symbol, hint, needle, cond in [
        ('ChangePlanScreen', 'manage/change_plan', 'ChangePlanCoordinator(', 'Internet change plan'),
        ('ShiftLocationScreen', 'manage/shift_location', 'ShiftLocationCoordinator(', 'Shift location'),
        ('ActiveAddonsScreen', 'active_addons', 'ActiveAddonsCoordinator(', 'Remove mobile subscription'),
        ('SimDeliveryOptionsView', 'sim_delivery_options', 'SimDeliveryOptionsCoordinator(', 'SIM replacement')]:
        f(party, symbol, hint, 'manage/party_id_selection', needle, 'Open selected service', cond)
    f(party, 'MultiSimPopupScreen', 'multi_sim_popup', 'manage/party_id_selection', 'MultiSimPopupCoordinator(', 'Choose SIM', 'Multi-SIM account')
    b.note('Company popup occurs only for partyIds.length > 1. Generic mobileDevices and mobileCloseAccountNew branches are no-op. Internet cessation is intercepted before the generic navigator, shown separately.')

    home = start('prepaid-conversion', 'Convert prepaid to postpaid', 'Manage', 'MobilePlanListingScreen', 'manage/pre_to_post')
    detail = f(home, 'MobilePlanDetailsScreen', 'manage/pre_to_post', 'pre_to_post/mobile_plan_listing', 'MobilePlanDetailsCoordinator(', 'Select postpaid plan')
    party = f(detail, 'SelectPartyIdScreen', 'manage/party_id_selection', 'pre_to_post/mobile_plan_details', 'SelectPartyIdCoordinator(', 'Select account', 'Company/account selection needed')
    checkout = f(party, 'CheckoutViewScreen', 'pre_to_post', 'manage/party_id_selection', 'CheckoutCoordinator(', 'Review conversion')
    b.note('Important-to-know and result UI are rendered within this flow; native close/landing calls are lifecycle exits.')

    home = start('sim-delivery', 'SIM replacement: address, identity and review', 'Manage', 'SimDeliveryOptionsView', 'sim_delivery_options')
    addr = f(home, 'AddressPopupScreen', 'address_popup', 'sim_delivery_options/coordinator', 'AddressPopupCoordinator(', 'Existing delivery address', 'Address selection available')
    loc = f(home, 'SelectLocationView', 'sim_replacement/add_address', 'sim_delivery_options/coordinator', 'SelectLocationCoordinator(', 'New address', 'Add address action selected')
    addaddr = f(loc, 'AddAddressView', 'sim_replacement/add_address/add_address', 'sim_replacement/add_address/select_location', 'AddAddressCoordinator(', 'Enter address details')
    review = f(addaddr, 'ReviewContactDetailsView', 'review_contact_details', 'add_address/add_address/coordinator', 'ReviewContactDetailsCoordinator(', 'Review delivery contact')
    checkout = f(home, 'ReviewOrderScreenView', 'review_order_screen', 'sim_delivery_options/coordinator', 'ReviewOrderScreenCoordinator(', 'Review replacement', 'Delivery and verification completed')
    success = f(checkout, 'SimReplacementSuccessView', 'sim_replacement_success', 'review_order_screen', 'SimReplacementSuccessCoordinator(', 'Replacement submitted', 'Submit success')
    user = f(success, 'ESimUserDetailsView', 'esim_user_details', 'sim_replacement_success', 'ESimUserDetailsCoordinator(', 'Activate eSIM', 'Eligible eSIM result')
    f(user, 'ViewQrCodeBottomSheetView', 'view_qr_code_bottom_sheet', 'esim_user_details', 'ViewQrCodeBottomSheetCoordinator(', 'Show activation QR', 'QR action selected')
    f(home, 'UaePassBottomSheetView', 'uae_pass_bottom_sheet', 'sim_delivery_options', 'UaePassBottomSheetCoordinator(', 'UAE PASS prompt', 'UAE PASS branch')
    b.note('Shared delivery screens also serve mobile-plan purchase. Address and verification branches can rejoin the owning purchase checkout; review screen depends on parent order type.')

    home = start('sim-identity', 'SIM and eSIM verification capabilities', 'Manage', 'SimDeliveryOptionsView', 'sim_delivery_options')
    auth = f(home, 'UaePassOnboardedUserAuthenticationView', 'uae_pass_onboarded_user_authentication', 'sim_delivery_options/coordinator', 'UaePassOnboardedUserAuthenticationCoordinator(', 'Authenticate with UAE PASS', 'UAE PASS onboarded-user route')
    f(auth, 'UaePassOnboardedUserVerificationView', 'uae_pass_onboarded_user_verification', 'uae_pass_onboarded_user_authentication', 'UaePassOnboardedUserVerificationCoordinator(', 'Verify user', 'Verification response requires this step')
    f(auth, 'UaePassOnboardedUserErrorView', 'uae_pass_onboarded_user_error', 'sim_delivery_options/coordinator', 'UaePassOnboardedUserErrorCoordinator(', 'Verification failed', 'UAE PASS error')
    service(auth, 'uaepass', 'UAE PASS app / document sharing', 'F', 'uae_pass_onboarded_user_authentication', 'UAE', 'Authentication or document sharing requested')
    consent = f(home, 'EfrConsentView', 'efr_consent', 'sim_delivery_options/coordinator', 'EfrConsentCoordinator(', 'Face verification consent', 'EFR identity branch')
    guide = f(consent, 'EfrGuidelinesView', 'efr_guidelines', 'sim_delivery_options/coordinator', 'EfrGuidelinesCoordinator(', 'Face capture instructions')
    sdk = service(guide, 'efr', 'Native EFR camera / liveness SDK', 'F', 'efr_guidelines', 'startFaceScanning')
    result = f(guide, 'EidRetrieveSuccessView', 'eid_retrieve_success', 'sim_delivery_options/coordinator', 'EidRetrieveSuccessCoordinator(', 'Identity retrieved', 'Successful EFR response')
    f(home, 'EFRGuidelinesErrorView', 'efr_guidelines_error', 'sim_delivery_options/coordinator', 'EFRGuidelinesErrorView(', 'Identity verification error', 'Identity/EFR failure')

    home = start('business-recommendations', 'Business fixed recommended addon purchase', 'Shop', 'RecommendedOffersViewAllScreen', 'recommended_offers')
    d = decision(home, 'offer', 'Fixed addon without PEGA?', "offerType=fixed && offerCategory=addon && submitToPega=false", 'recommended_offers_helper', "== 'addon'")
    party = f(d, 'PartyIdScreenForRecommendedOffers', 'recommended_offers', 'recommended_offers', 'PartyIdScreenForRecommendedOffers(', 'Choose company', 'Fixed addon without PEGA')
    acc = f(party, 'PartyIdAccountsScreenForRecommendedOffers', 'recommended_offers', 'recommended_offers', 'PartyIdAccountsScreenForRecommendedOffers(', 'Choose eligible accounts')
    benefit = f(acc, 'AddOnBenefitsRecommendedOffersScreen', 'recommended_offers', 'recommended_offers', 'AddOnBenefitsRecommendedOffersScreen(', 'Review addon benefits')
    checkout = f(benefit, 'CheckoutScreen', 'common/checkout', 'recommended_offers_checkout', 'CheckoutScreen(', 'Review recommended addon')
    f(benefit, 'NumberSelectionForBuyAddonsScreen', 'number_selection_for_buy_addons', 'recommended_offers_add_on_benefits', 'RecommendedOfferNumberSelectionForBuyAddonsCoordinator(', 'Select addon numbers', 'Fixed-addon number-selection branch')
    f(checkout, 'TermsAndConditionsScreen', 'common/terms_and_conditions', 'recommended_offers_checkout', 'TermsAndConditionsCoordinator(', 'Read purchase terms')
    service(d, 'native-shop', 'Native Shop recommendation dispatch', 'F', 'recommended_offers_helper', 'navigateToShop', 'All other offer conditions')

    home = start('bfm-fixed-addons', 'BFM fixed addons and managed devices', 'Shop', 'AddonShopScreen', 'addons/addons_shop')
    category = f(home, 'AddonsCategoryViewAllScreen', 'addons_category_view_all', 'addons', 'AddonsCategoryViewAllCoordinator(', 'View all category')
    benefit = f(home, 'AddonBenefitsScreen', 'addons/addons_benefets', 'addons', 'AddonsBenefitsCoordinator(', 'Select addon')
    child = f(benefit, 'AddonsShowChildAccountsScreen', 'addons_show_child_accounts', 'addons_benefets', 'AddonsShowChildAccountsCoordinator(', 'Choose child accounts', 'Selected addon requires child-account selection')
    f(benefit, 'NumberSelectionForBuyAddonsScreen', 'number_selection', 'addons_benefets', 'NumberSelection', 'Select numbers', 'Number selection required')
    checkout = f(benefit, 'CheckoutScreen', 'common/checkout', 'addons_and_recommended_offers_checkout', 'CheckoutScreen(', 'Review addon purchase')
    f(home, 'ManageAddonScreen', 'delete_addons/manage_addon', 'dashboard/account/subscriptions', 'ManageAddonCoordinator(', 'Manage installed addon', 'Entered from account subscriptions')
    b.note('This active fixed-addon family differs from Shop addons revamp. ManagedDevicesCheckoutCoordinator also renders the same common CheckoutScreen from BFM subscriptions.')

    home = start('fixed-main-number', 'Change fixed main number', 'Manage', 'PartyIdSearchScreenForChangeMainNumber', 'change_main_number')
    select = f(home, 'SelectMainNumberScreen', 'change_main_number', 'change_main_number/party_id_search', 'SelectMainNumberCoordinator(', 'Choose replacement main number')
    checkout = f(select, 'ChangeMainNumberCheckoutScreen', 'change_main_number', 'change_main_number/select_main_number', 'ChangeMainNumberCheckoutCoordinator(', 'Review change')
    f(checkout, 'ChangeMainNumberSuccessScreen', 'change_main_number', 'change_main_number', 'ChangeMainNumberSuccessScreen(', 'Number change submitted', 'Submit success')

    home = start('internet-closure', 'Close internet account / retention', 'Manage', 'ChurnExitPartyIdSearchScreen', 'domain_activation_management/party_id_search')
    party = f(home, 'PartyIdAccountsScreen', 'domain_activation_management/party_id_search', 'domain_activation_management/party_id_search', 'PartyIdAccounts', 'Select fixed account')
    reason = f(party, 'SelectReasonScreen', 'churn_exit/reasons', 'domain_activation_management/party_id_search', 'SelectReason', 'Choose closure reason')
    offers = f(reason, 'AutomatedOffersScreen', 'churn_exit/automated_offers', 'churn_exit', 'AutomatedOffersScreen(', 'Retention offers', 'API/business response offers retention')
    child = f(offers, 'ChurnExitChildAccountScreen', 'churn_exit', 'churn_exit', 'ChurnExitChildAccountScreen(', 'Child accounts', 'Child-account offer branch')
    checkout = f(offers, 'CheckoutScreen', 'churn_exit/checkout', 'churn_exit', 'CheckoutScreen(', 'Review retention offer')
    trouble = f(reason, 'TroubleShootingScreen', 'churn_exit', 'churn_exit', 'TroubleShootingScreen(', 'Troubleshoot', 'Troubleshooting branch')
    f(trouble, 'TroubleShootingWebScreen', 'churn_exit', 'churn_exit', 'TroubleShootingWebScreen(', 'Open troubleshooting site')
    f(trouble, 'TroubleShootingErrorScreen', 'churn_exit', 'churn_exit', 'TroubleShootingErrorScreen(', 'Troubleshooting error', 'API/site error')
    close = f(reason, 'AccountClosureScreen', 'churn_exit', 'churn_exit', 'AccountClosureScreen(', 'Proceed to account closure')
    f(close, 'CollectionOfDevicesScreen', 'churn_exit', 'churn_exit', 'CollectionOfDevicesScreen(', 'Device collection', 'Devices must be collected')
    f(close, 'ContactAtLocationScreen', 'churn_exit', 'churn_exit', 'ContactAtLocationScreen(', 'Site contact', 'Contact required')
    pay = f(close, 'PaymentMethodScreen', 'churn_exit', 'churn_exit', 'PaymentMethodScreen(', 'Settle outstanding balance', 'Payment due')
    f(pay, 'PaymentWebViewScreen', 'churn_exit', 'churn_exit', 'PaymentWebViewScreen(', 'Payment portal')
    f(close, 'TermsAndConditionScreen', 'churn_exit', 'churn_exit', 'TermsAndConditionScreen(', 'Closure terms')
    f(close, 'OrderFailureScreen', 'churn_exit', 'churn_exit', 'OrderFailureScreen(', 'Submission failed', 'Failure response')
    f(close, 'SuccessScreen', 'domain_activation_management/success', 'churn_exit', 'SuccessScreen(', 'Closure / retention submitted', 'Successful result')
    b.note('Active entry is MenuSubcategoryCoordinator internetCeaseAccount interception after account filtering, or ChurnExitCM; generic navigator no-op does not disable it. Payment/troubleshooting WebViews are Flutter-owned screens.')

    native_flows(b, node, evidence, add)
    extra_flows(b, node, evidence)


def native_flows(b, node, evidence, add):
    def ref(repo, region, target):
        return evidence(repo, region, target)

    def edge(src, repo, target, region, label='Continue', condition='', hint=''):
        dest = node(repo, target, hint)
        b.edge(src, dest, label, [ref(repo, region, target)], condition=condition)
        return dest

    def journey(key, title, family, root, method):
        b.journey(key, title, family, 'Native branch selected by backend menu / URL, role and account eligibility; platform differences are shown separately.')
        entry = node('F', 'ShopHomeScreen' if family == 'Shop' else 'MenuSubcategoryScreen', 'shop_home' if family == 'Shop' else 'manage/menu_subcategory')
        b.entry(entry)
        a = node('A', root)
        ev = evidence('A', 'flutter/FlutterNavigationHandler', root)
        b.edge(entry, a, 'Android native entry', [ev], condition=method)
        return entry, a

    entry, devices = journey('native-devices', 'Buy a device: native and Flutter handoffs', 'Shop', 'ShopDevicesActivity', 'Device category / device deep link')
    detail = edge(devices, 'A', 'ShopDevicesDetailActivity', 'shop_devices', 'Select device')
    ev = evidence('A', 'ShopDevicesDetailActivity', 'dataPromoEnabled')
    gate = b.decision('promotion', 'Eligible account selection needed?', "loginType != QUICK_ACCESS && device.dataPromoEnabled == '1'", [ev])
    b.edge(detail, gate, 'Buy / preorder', [ev])
    selector = node('F', 'AccountWithPartyIdScreen', 'account_with_party_id')
    b.edge(gate, selector, 'Choose eligible company/account (Flutter)', [evidence('A', 'ShopDevicesDetailActivity', 'navigateToSelectAccountFlow'), evidence('F', 'select_account_with_party_id_cm', 'AccountWithPartyIdCoordinator(')], condition='Not QUICK_ACCESS and data promotion enabled')
    b.edge(selector, detail, 'Return selected account; reserve order', [evidence('F', 'account_with_party_id', 'onAccountSelected'), evidence('A', 'flutter/FlutterNavigationHandler', 'callReserveOrderApi')], kind='return')
    addr = edge(detail, 'A', 'ShopUserAddressesActivity', 'ShopDevicesDetailActivity', 'Reserve successful / delivery', 'Reservation succeeds')
    edge(detail, 'A', 'ShopDeviceStockErrorActivity', 'ShopDevicesDetailActivity', 'Stock unavailable', 'Reserve stock error')
    web = edge(detail, 'A', 'WebPageActivity', 'ShopDevicesDetailActivity', 'Terms', 'Read terms action')
    ev = evidence('I', 'FlutterLinkable+Sales', 'navigateToDeviceShopList')
    i = node('I', 'DeviceVC', 'DeviceVC')
    b.edge(entry, i, 'iOS device listing', [ev])
    edge(i, 'I', 'DeviceDetailVC', 'Device', 'Select device')
    b.note('QUICK_ACCESS/no-data-promotion skips the Flutter account selector. Native stock/reservation, delivery, review and payment retain native ownership.')

    specs = [
        ('native-mobile', 'Mobile plans from native URL / legacy catalogue', 'Shop', 'ShopMobilePlansInventoryActivity', 'URL mobilePlans / planDetail, legacy inventory', 'shop/', [('ShopMobilePlanDetailsActivity', 'Select plan'), ('ShopUserAddressesActivity', 'Choose delivery address')]),
        ('native-addons', 'Native addon / prepaid Shop purchase', 'Shop', 'ShopAddonSectionsInventoryActivity', 'Legacy/native inventory or prepaid addon entry', 'shop/', [('ShopAddonDetailsActivity', 'Select addon'), ('ShopAddonAccountsSelectionActivity', 'Select eligible accounts'), ('ShopCartActivity', 'Review addon cart')]),
        ('native-insurance', 'Business insurance', 'Shop', 'BusinessProtectActivity', 'BusinessInsuranceType menu', 'business_insurance/', [('BusinessInsuranceActivity', 'Select protection'), ('BusinessInsuranceFormActivity', 'Insurance enquiry form')]),
        ('native-change-plan', 'Change mobile plan: native purchase branch', 'Manage', 'ChangePlansInventoryActivity', 'changeMobilePlan menu', 'change_plan/', [('ChangePlanActivity', 'Select change plan'), ('ChangePlanEligibleAccountsActivity', 'Eligible accounts'), ('ChangePlanDetailsActivity', 'Plan details'), ('ChangePlanReviewOrderActivity', 'Review change order')]),
        ('native-data-cap', 'Data cap and usage limit', 'Manage', 'DataCapEligibleAccountsActivity', 'changeCapLimit or changeUsageLimit; TYPE_DATACAP versus TYPE_USAGE_LIMIT', 'datacap/', [('DataCapModifyActivity', 'Modify cap / limit')]),
        ('native-app-store', 'App Store spending limit', 'Manage', 'AppStoreLimitActivity', 'appStoreUsage menu', 'credit_limit/', [('AppStoreModifyActivity', 'Modify spending limit')]),
        ('native-credit', 'Credit limit: native Manage journey', 'Manage', 'CreditAndStoreOptionsActivity', 'creditLimit menu; separate from BFM Flutter UpdateCreditLimit', 'credit_limit/', [('UpdateCreditLimitPartyIdActivity', 'Select company'), ('UpdateCreditLimitAccountsActivityBulk', 'Select accounts'), ('UpdateCreditLimitModifyActivityBulk', 'Set limits'), ('UpdateCreditLimitReviewSubmitActivityBulk', 'Review and submit')]),
        ('native-relocation', 'Business relocation', 'Manage', 'ResetLocationMainActivity', 'businessRelocation menu', 'reset_location/', [('ResetLocationAccountsActivity', 'Select account'), ('ResetLocationStepsActivity', 'Relocation steps'), ('ResetLocationMapActivity', 'New service location')]),
        ('native-antivirus', 'Antivirus licenses', 'Manage', 'AntivirusLicensesMainActivity', 'antivirusLicenses menu', 'antivirus_licenses/', [('AntivirusLicenseDetailsActivity', 'License details')]),
        ('native-mobile-close', 'Close mobile account: native branch', 'Manage', 'CessationEligibleAccountsActivity', 'mobileCloseAccountOld menu', 'cessation/', [('CessationReasonSelectionActivity', 'Closure reason'), ('CessationDetailActivity', 'Review closure')]),
    ]
    for key, title, family, root, condition, region, chain in specs:
        entry, src = journey(key, title, family, root, condition)
        for target, label in chain:
            src = edge(src, 'A', target, region, label)
        # Explicit native branch alternatives evidenced by Intent/controller calls.
        extras = {
            'native-change-plan': [('ChangePlanEligibleAccountsActivity', 'ChangePlanAccountSearchActivity', 'Search accounts'), ('ChangePlanEligibleAccountsActivity', 'AccountsCompatibilityErrorActivity', 'Incompatible selection')],
            'native-data-cap': [('DataCapEligibleAccountsActivity', 'DataCapSearchActivity', 'Search accounts')],
            'native-app-store': [('AppStoreLimitActivity', 'AppStoreSearchActivity', 'Search accounts')],
            'native-credit': [('UpdateCreditLimitReviewSubmitActivityBulk', 'UpdateCreditLimitSuccessActivity', 'Submit success'), ('UpdateCreditLimitReviewSubmitActivityBulk', 'UpdateCreditLimitErrorActivity', 'Submit failure')],
            'native-mobile-close': [('CessationReasonSelectionActivity', 'CessationCommentsActivity', 'Additional comments'), ('CessationEligibleAccountsActivity', 'AccountsSearchActivity', 'Search accounts')],
        }
        for parent, target, label in extras.get(key, []):
            edge(node('A', parent), 'A', target, region, label, 'Action or response selects this branch')
        ios = {
            'native-mobile': ('ShopPackagesListViewController', 'FlutterLinkable+Sales', 'moveToShopPlanVC', ''),
            'native-change-plan': ('ShopPackagesListViewController', 'FlutterLinkable+ManageRevamp', 'PackageTypeChangePlan', ''),
            'native-data-cap': ('AccountLimitVC', 'FlutterLinkable+ManageRevamp', 'navigateAccountLimit', 'SwiftSections/'),
            'native-antivirus': ('AntivirusLicensesVC', 'FlutterLinkable+ManageRevamp', 'andIdentifier: Constant.ViewControllers.antivirusLicenses', ''),
            'native-mobile-close': ('AccountCessationChooseAccountVC', 'FlutterLinkable+ManageRevamp', 'getAccountCessationVC', ''),
        }
        if key in ios:
            symbol, part, needle, hint = ios[key]
            dest = node('I', symbol, hint)
            b.edge(entry, dest, 'iOS native entry', [evidence('I', part, needle)], condition=condition)
            if key == 'native-mobile':
                detail = edge(dest, 'I', 'ShopPlanDetailsViewController', '/Shop/', 'Select plan')
                delivery = edge(detail, 'I', 'ShopSetDeliveryInfoViewController', '/Shop/', 'Delivery information')
                edge(delivery, 'I', 'ShopReviewOrderViewController', '/Shop/', 'Review order')
            if key == 'native-change-plan':
                detail = edge(dest, 'I', 'ChangePlanDetailVC', 'ShopPackagesListViewController.m', 'Select change plan')
                device = edge(detail, 'I', 'ChangePlanMobileDeviceVC', 'ChangePlanDetailVC.m', 'Select device', 'Plan includes device')
                edge(detail, 'I', 'ChangePlanReviewOrderVC', 'ChangePlanDetailVC.m', 'Review change order')
                b.edge(device, detail, 'Return device choice', [evidence('I', 'ChangePlanMobileDeviceVC.m', 'ChangePlanDetailVC')], kind='return')
            if key == 'native-mobile-close':
                reason = edge(dest, 'I', 'AccountCessationReasonsVC', 'AccountCessation', 'Closure reason')
                edge(reason, 'I', 'AccountCessationReviewVC', 'AccountCessation', 'Review closure')
            if key == 'native-data-cap':
                detail = node('I', 'AccountLimitDetailVC', 'SwiftSections/')
                b.edge(dest, detail, 'Modify usage / data cap', [evidence('I', 'AccountLimitCap', 'AccountLimitDetailCoordinator(')])
                for s in ('AccountLimitFilterViewController', 'AccountLimitBottomSheetVC'):
                    dest2 = node('I', s, 'SwiftSections/')
                    needle2 = 'AccountLimitFilterCoordinator(' if s == 'AccountLimitFilterViewController' else 'AccountLimitBottomSheetCoordinator('
                    b.edge(detail if s.endswith('VC') else dest, dest2, 'Filter / choose amount', [evidence('I', 'AccountLimitCap', needle2)], condition='Action selected')
        else:
            needle = {'native-credit':'NavigateToCreditLimitLink', 'native-relocation':'NavigateToBusinessRelocationLink', 'native-insurance':'OpenBusinessInsuranceLink', 'native-addons':'OpenAddonsFlowLink'}.get(key)
            part = 'FlutterLinkable+Sales' if key == 'native-insurance' else 'FlutterLinkable+Shop' if key == 'native-addons' else 'FlutterLinkable+ManageRevamp'
            if key == 'native-app-store':
                ev = evidence('F', 'channel_controller.dart', 'FlutterMethod.navigateToAppStoreLimit,')
                unresolved = b.unresolved('ios-vendor', 'iOS App Store limit bridge unresolved', [ev], 'Flutter sends navigateToAppStoreLimit, but no matching iOS FlutterLink handler/registration was found; do not substitute the credit-limit handler.')
                b.edge(entry, unresolved, 'iOS bridge destination unresolved', [ev], condition=condition)
            else:
                needles = {'native-credit': 'method: FlutterConstant.Methods.navigateToCreditLimit,', 'native-relocation': 'method: FlutterConstant.Methods.navigateToBusinessRelocation,', 'native-insurance': 'businessInfoWrapper.start(', 'native-addons': 'navigateToVirtualPrePaidShopVC('}
                ev = evidence('I', part, needles[key])
                unresolved = b.unresolved('ios-vendor', 'iOS native vendor / menu router destination', [ev], 'Bridge routing is verified; concrete controller chain remains unresolved in this view. Do not assume Android parity.')
                if key == 'native-addons':
                    prepaid = node('F', 'PrepaidHomeScreen', 'dashboard/prepaid_home')
                    b.entry(prepaid)
                    b.edge(prepaid, unresolved, 'iOS virtual prepaid addon shop', [ev], condition='isVirtualPrepaidUser = true; linked account and credit response required')
                else:
                    b.edge(entry, unresolved, 'iOS native entry', [ev], condition=condition)

    entry, root = journey('native-dnd', 'Do not disturb / blocking preferences', 'Manage', 'DNDOptionsActivity', 'doNotDisturb menu')
    account = edge(root, 'A', 'DNDAccountSelectionActivity', 'dnd/', 'Choose account', 'Multiple accounts or account selection needed')
    for target in ('DNDCallBlockUnblockActivity', 'DNDSmsBlockUnblockActivity', 'DNDCategoryBlockUnblockActivity'):
        edge(account, 'A', target, 'dnd/', 'Block / unblock preference', 'Selected DND option')
    ios = node('I', 'DNDMainListingViewController')
    b.edge(entry, ios, 'iOS DND', [evidence('I', 'FlutterLinkable+ManageRevamp', 'navigateDoNotDisturb')])
    for target in ('DNDPromotionalSmsAndCallBlockVC', 'DNDCategoryBlockUnblockVC'):
        edge(ios, 'I', target, '/DND/', 'DND selection / preference', 'Menu / blocking category action')

    b.note('DNDActionSheetViewController callers are commented; DNDChooseAccountVC has no verified active incoming producer in this branch. Neither is asserted as a live navigation step.')

    entry, root = journey('native-vsaas', 'Video surveillance licenses, cameras and reports', 'Manage', 'VsaasMainActivity', 'surveillanceSolution menu')
    for target in ('VsaasSubscriptionActivity', 'ReportsMainActivity', 'VsaasCameraDetailsActivity'):
        edge(root, 'A', target, 'vSaas/', 'Select license / reports / camera', 'Selected action')
    cam = node('A', 'VsaasCameraDetailsActivity')
    for target in ('VsaasEventActivity', 'VsaasArchiveActivity', 'VsaasVideoFullScreenActivity'):
        edge(cam, 'A', target, 'vSaas/', 'Camera playback / event', 'Selected action')
    ios = node('I', 'CamerasListViewController')
    b.edge(entry, ios, 'iOS camera list', [evidence('I', 'FlutterLinkable+ManageRevamp', 'andIdentifier: Constant.ViewControllers.cameraList')])
    for target in ('CameraDetailsViewController', 'VSaaSReportsVC', 'VsaasArchiveViewController', 'VsaasVideoViewController'):
        edge(ios, 'I', target, '/VSaaS/', 'Camera / reports / playback', 'Selected action')

    entry, root = journey('native-business-edge', 'Business Edge password and fixed voice management', 'Manage', 'BusinessEdgeOptionsActivity', 'businessEdge menu')
    acc = edge(root, 'A', 'BusinessEdgeAccountsActivity', 'business_edge/', 'Choose account')
    for target in ('ResetInternetPasswordActivity', 'BusinessEdgeFixedVoiceActivity'):
        edge(acc, 'A', target, 'business_edge/', 'Selected service', 'Internet password or fixed voice')
    voice = node('A', 'BusinessEdgeFixedVoiceActivity')
    edge(voice, 'A', 'FixedVoiceDetailsActivity', 'business_edge/', 'Number details')
    ev = evidence('I', 'FlutterLinkable+ManageRevamp', 'method: FlutterConstant.Methods.navigateToBusinessEdge,')
    u = b.unresolved('ios-business-edge', 'iOS Business Edge menu router', [ev], 'Concrete destination depends on supplied ProfileMenu; controller chain not confirmed here.')
    b.edge(entry, u, 'iOS native entry', [ev])


def extra_flows(b, node, evidence):
    def link(src, repo, target, region, needle=None, label='Continue', condition='', hint='', kind='navigation'):
        dest = node(repo, target, hint)
        ev = evidence(repo, region, needle or target)
        b.edge(src, dest, label, [ev], condition=condition, kind=kind)
        return dest

    b.journey('device-trade-in', 'Device trade-in and assured buyback', 'Shop', 'Shop trade-in banner uses Flutter selection, followed by native-hosted trade-in website.')
    home = node('F', 'ShopHomeScreen', 'shop_home');b.entry(home)
    info = link(home, 'F', 'TradeInInfoView', 'shop_menu_navigation_helper', 'TradeInInfoCoordinator(', 'Trade-in banner', 'deviceShop / tradeIn banner')
    party = link(info, 'F', 'PartyIdSelectionView', 'device_trade_in', 'PartyIdSelectionCoordinator(', 'Choose company')
    ev = evidence('F', 'device_trade_in', 'openURLInWebView')
    native = b.unresolved('tradein-web', 'Native trade-in website', [ev], 'Flutter delegates openURLInWebView; the platform-specific WebView destination depends on native handler.')
    b.edge(party, native, 'Continue to trade-in partner', [ev])
    link(home, 'F', 'DeviceAssuredBuyBackScreen', 'core/deeplink_manager/routers/url/shop_deeplink_router', 'DeviceAssuredBuyBackScreen(', 'Assured buyback', 'Verified incoming buyback/account action')

    b.journey('native-internet', 'Native internet / UCaaS catalogue purchase', 'Internet orders', 'Legacy/native catalogue entry remains distinct from Flutter Internet bundle and fixed-number-porting journeys.')
    root = node('A', 'ShopInventoryActivity');b.entry(root)
    detail = link(root, 'A', 'ShopUCaasDetailsActivity', 'shop/', label='Select internet bundle')
    loc = link(detail, 'A', 'ShopUcaasLocationSetupActivity', 'ShopUCaasDetailsActivity', label='Set service location')
    link(loc, 'A', 'UcaasAddressSearchActivity', 'ShopUcaasLocationSetupActivity', label='Search address', condition='Address search requested')
    config = link(loc, 'A', 'ShopUcaasPlanConfigrationActivity', 'ShopUcaasLocationSetupActivity', label='Configure plan', condition='Location serviceability succeeds')
    numbers = link(config, 'A', 'ShopUcaasAdditionalLinesActivity', 'ShopUcaasPlanConfigrationActivity', label='Additional lines')
    site = link(numbers, 'A', 'ShopUcaasSiteConfigActivity', 'ShopUcaasAdditionalLinesActivity', label='Site configuration')
    cart = link(site, 'A', 'ShopUcaasCartActivity', 'ShopUcaasSiteConfigActivity', label='Review cart')
    ev = evidence('A', 'ShopUcaasCartActivity', 'viewPDF')
    pdf = b.service('terms', 'Platform PDF viewer / UCaaS terms', [ev])
    b.edge(cart, pdf, 'Read terms', [ev], kind='service')
    ev = evidence('A', 'ShopUcaasCartActivity', 'dialog_shop_success_screen')
    result = b.special('result', 'Native success / callback dialog', 'terminal', [ev])
    b.edge(cart, result, 'Submission result', [ev], condition='Submit succeeds or callback is required')
    ev = evidence('I', 'CoreSwift/Source/Manager/DeepLinkManager/ShopNavigator', 'moveTo')
    unresolved = b.unresolved('ios-internet', 'iOS native internet catalogue router', [ev], 'Platform-native catalogue destination depends on product/router; do not assume Android UCaaS controller sequence.')
    b.entry(unresolved)

    b.journey('native-shop-checkout', 'Native device/mobile/addon delivery and payment', 'Shop', 'Continuation of native purchase variants; Flutter mobile/addon payment remains a separate flow.')
    root = node('A', 'ShopUserAddressesActivity');b.entry(root)
    cart = link(root, 'A', 'ShopCartActivity', 'ShopUserAddressesActivity', label='Review order after delivery')
    # Addon details can bypass address/cart to an immediate payment branch.
    detail = node('A', 'ShopAddonDetailsActivity');b.entry(detail)
    card = link(detail, 'A', 'CreditCardPaymentActivity', 'ShopAddonDetailsActivity', label='Card payment', condition='Immediate payable addon branch')
    link(card, 'A', 'AutoPayConsentActivity', 'CreditCardPaymentActivity', label='Auto Pay consent', condition='Auto Pay consent required')
    link(card, 'A', 'PaymentPortalActivity', 'CreditCardPaymentActivity', label='Gateway portal', condition='Card/payment URL returned')
    ios = node('I', 'ShopSetDeliveryInfoViewController');b.entry(ios)
    review = link(ios, 'I', 'ShopReviewOrderViewController', '/Shop/', label='Review delivery / order')
    b.note('Android stock/reservation errors, card consent and gateway returns follow native controllers. Native success dialogs are results, not invented screen classes.')

    # Dedicated source-proven additions to existing native-license and camera views.
    j = next(j for j in b.journeys if j['id'] == 'native-antivirus');b.current = j
    licenses = node('I', 'AntivirusLicensesVC')
    detail = link(licenses, 'I', 'AntivirusLicensesDetailVC', 'AntivirusLicensesVC.m', label='License details')
    link(detail, 'I', 'AntivirusLicenseSuccessVC', 'AntivirusLicensesDetailVC.m', label='License action successful', condition='License response succeeds')
    j = next(j for j in b.journeys if j['id'] == 'native-vsaas');b.current = j
    camera = node('I', 'CameraDetailsViewController')
    event = link(camera, 'I', 'VsaasEventsViewController', '/VSaaS/', label='Camera events')
    link(event, 'I', 'EventsTimeFilterViewController', '/VSaaS/', label='Filter event period', condition='Filter action')
    link(camera, 'I', 'VsaasVideoFullViewController', '/VSaaS/', label='Fullscreen playback', condition='Fullscreen action')
