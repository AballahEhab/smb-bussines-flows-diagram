"""Login, shell, account, billing and identity journeys, checked against source.

Edges use executable call evidence plus coordinator destination evidence. Imported
symbols and declarations alone never establish a transition.
"""
import re
from scripts.flow_builder import ROOTS, friendly


def build(b):
    for repo in ROOTS:
        b._index(repo)

    source_paths = {}
    clean_cache = {}
    for repo in ROOTS:
        source_paths[repo] = sorted(str(p.relative_to(ROOTS[repo])) for p in ROOTS[repo].rglob('*') if p.suffix in ({'.dart'} if repo == 'F' else {'.swift','.m','.kt','.java'}) and not any(x in p.parts for x in ('Pods','.git','build','.dart_tool')))

    def declaration(repo, symbol, hint=''):
        if repo == 'I' and symbol in ('UserAdminManagementVC','AddUserVC','ConfirmationBottomSheetVC') and not hint: hint = 'SwiftSections'
        if repo == 'I' and symbol == 'MakePaymentViewController' and not hint: hint = 'Bills And Payment'
        rows = [(p, l) for p, l in b._classes[repo].get(symbol, []) if hint in p]
        if repo == 'I' and len(rows) > 1:
            implementation = [(p,l) for p,l in rows if not p.endswith('.h')]
            if len(implementation) == 1: rows = implementation
        if len(rows) != 1:
            raise ValueError((repo, symbol, hint, rows))
        return rows[0][0]

    def mask_comments(content):
        # Preserve quoted MIME values (e.g. "image/*") and URLs while masking
        # comments; a regex that treats those strings as comments loses callers.
        token = r"(\"\"\"[\s\S]*?\"\"\"|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')|(/\*[\s\S]*?\*/|//[^\n]*)"
        return re.sub(token, lambda m: m[1] if m[1] is not None else ''.join('\n' if c == '\n' else ' ' for c in m[0]), content)

    def evidence(repo, needle, hint='', occurrence=1):
        """Find a real call/reference, excluding declarations, imports and comments."""
        matches = []
        paths = [p for p in source_paths[repo] if hint in p]
        for path in paths:
            original = b.text(repo, path)
            # Keep newlines and positions while masking comments.
            clean = mask_comments(original)
            lines = original.splitlines()
            for lineno, line in enumerate(clean.splitlines(), 1):
                if needle not in line or (needle.isidentifier() and not re.search(r'\b'+re.escape(needle)+r'\b',line)) or line.lstrip().startswith(('#import','@implementation')) or re.search(r'^\s*(import|package|class|interface|struct|enum|@interface)\b', line):
                    continue
                # Constructor or function definition is not a destination call.
                if re.match(r'^\s*(?:const\s+)?' + re.escape(needle.rstrip('(')) + r'\s*\(', line) and re.search(r'\b(required|super\.|this\.)', line):
                    continue
                matches.append({'repo': repo, 'path': path, 'line': lineno, 'excerpt': lines[lineno-1].strip()[:350]})
        if len(matches) < occurrence:
            raise ValueError(f'No executable call {repo}:{hint}: {needle}')
        return matches[occurrence-1]

    def node(repo, symbol, hint='', **kw):
        if repo == 'I': hint = declaration(repo, symbol, hint)
        return b.screen(repo, symbol, hint, **kw)

    def f(symbol, hint='', **kw): return node('F', symbol, hint, **kw)
    def a(symbol, hint='', **kw): return node('A', symbol, hint, **kw)
    def i(symbol, hint='', **kw): return node('I', symbol, hint, **kw)

    def link(start, end, call, hint, label, condition='', repo='F', kind='navigation', default=None):
        ev = evidence(repo, call, hint)
        return b.edge(start, end, label, [ev], condition=condition, kind=kind, default=default)

    def fn(start, target, call, hint, label, condition='', target_hint='', **kw):
        end = f(target, target_hint, **kw)
        source = evidence('F', call, hint)
        sources = [source]
        if call.rstrip('(').endswith('Coordinator'):
            # Rendering the coordinator's actual target is separate corroboration.
            coordinator_symbol = call.rstrip('(')
            coordinator_rows = b._classes['F'].get(coordinator_symbol, [])
            cp_hint = target_hint
            if len(coordinator_rows) > 1 and not cp_hint:
                cp_hint = declaration('F', target).split('/presentation/')[0].split('/views/')[0]
            cp = declaration('F', coordinator_symbol, cp_hint)
            try: sources.append(evidence('F', target + '(', cp))
            except ValueError: pass  # Some boundaries return a cached local variable.
        b.edge(start, end, label, sources, condition=condition)
        return end

    def nav_evidence(repo, target, path):
        content=b.text(repo,path)
        clean=mask_comments(content)
        lines=content.splitlines(); cleared=clean.splitlines()
        for lineno,line in enumerate(cleared,1):
            if not re.search(r'\b'+re.escape(target)+r'\b',line): continue
            if line.lstrip().startswith(('import','#import','@interface','@property','class','struct','enum')): continue
            if repo=='A':
                accepted = re.search(re.escape(target)+r'(?:::class(?:\.java)?|\.class)\b',line)
            else:
                nearby='\n'.join(cleared[lineno-1:lineno+3])
                accepted=(re.search(re.escape(target)+r'\.(?:instanceFromStoryboard|instantiate)',line)
                          or (re.search(re.escape(target)+r'\s*\(',line) and '=' in line)
                          or (re.search(r'\b'+re.escape(target)+r'\b',line) and '=' in line and re.search(r'viewControllerWith|instanceFromStoryboard|instantiate|alloc\]',nearby))
                          or ('viewControllerIdentifier' in line and '=' in line))
            if accepted:
                return {'repo':repo,'path':path,'line':lineno,'excerpt':lines[lineno-1].strip()[:350]}
        raise ValueError('No constructed navigation target '+repo+':'+path+':'+target)

    def native_internal(repo, symbols, label_overrides=None):
        """Only direct executable destination references in concrete native screens."""
        label_overrides = label_overrides or {}
        nodes = {}
        for symbol in symbols:
            if symbol in b._classes[repo]: nodes[symbol] = node(repo, symbol)
            else: nodes[symbol] = b.unresolved(repo + '-' + symbol, symbol, [evidence(repo, symbol)], notes='Native destination is referenced in executable routing but its concrete implementation is absent from this checkout.')
        for origin in symbols:
            if origin not in b._classes[repo]: continue
            path = declaration(repo, origin)
            if path.endswith('.h') and (ROOTS[repo] / (path[:-2] + '.m')).exists(): path = path[:-2] + '.m'
            for target in symbols:
                if target == origin: continue
                try: ev = nav_evidence(repo, target, path)
                except ValueError: continue
                # Preserve surrounding routing predicates and local data in details.
                lines = b.text(repo, path).splitlines()
                context = '\n'.join(lines[max(0, ev['line']-22):ev['line']+5])
                condition = 'User action / API result selects destination; inspect caller context'
                b.edge(nodes[origin], nodes[target], label_overrides.get((origin,target), 'Open ' + friendly(target)), [ev], condition=condition,
                       notes='Constructed native navigation target. Nearby guards are retained as context; they are not asserted as exact enclosing predicates.\n' + context)
        if repo == 'I':
            # Swift screens delegate navigation to the owning feature coordinator.
            # Collapse those executable coordinator/wrapper calls into screen edges.
            mapped = {}
            for target in symbols:
                if target not in b._classes[repo]: continue
                tp = declaration(repo, target)
                if '/Presentation/' not in tp: continue
                feature = tp.split('/Presentation/')[0] + '/'
                coordinator_paths = [p for p in source_paths[repo] if feature in p and ('Coordinator/' in p or 'Coordinator.swift' in p)]
                for cp in coordinator_paths:
                    try: rendered = evidence(repo, target + '.instanceFromStoryboard', cp)
                    except ValueError:
                        try: rendered = evidence(repo, target + '(', cp)
                        except ValueError: continue
                    for symbol in re.findall(r'\bclass\s+(\w+)', b.text(repo, cp)):
                        if symbol.endswith(('Coordinator','Wrapper')): mapped[symbol] = (target, rendered)
            existing = {(e['from'],e['to']) for e in b.edges if e['journey'] == b.current['id']}
            for origin in symbols:
                if origin not in b._classes[repo]: continue
                op = declaration(repo, origin)
                if '/Presentation/' not in op: continue
                feature = op.split('/Presentation/')[0] + '/'
                for boundary,(target, rendered) in mapped.items():
                    if target == origin or (nodes[origin],nodes[target]) in existing: continue
                    try: caller = evidence(repo, boundary + '(', feature)
                    except ValueError: continue
                    # Owning source may also declare its own coordinator; prefer an
                    # assignment or wrapper constructor over function signatures.
                    if caller['path'] == rendered['path']: continue
                    b.edge(nodes[origin],nodes[target],'Open ' + friendly(target),[caller,rendered],
                           notes='Screen-owned Swift coordinator / wrapper navigation. Source callback determines the optional branch.')
                    existing.add((nodes[origin],nodes[target]))
        return nodes

    # ------------------------------------------------------------------
    b.journey('login', 'Flutter login and sign-in choices', 'Login & registration',
              'The current app starts at Flutter login. Native login is obsolete and excluded from active journeys.')
    login = f('MainLoginScreen', label='Start • Flutter login')
    b.entry(login)
    email = fn(login, 'EmailLoginScreen', 'EmailLoginScreen(', 'bss/login/domain/viewmodel', 'Email and password', 'type == AppConstant.eand_login_type')
    otpemail = fn(login, 'EmailOtpLoginScreen', 'EmailOtpLoginCoordinator(', 'bss/login/domain/viewmodel', 'Email OTP', 'type == AppConstant.otp_login_type')
    uaepass = fn(login, 'UaePassScreen', 'UaePassCoordinator(', 'bss/login/domain/viewmodel', 'UAE PASS sign-in', 'type == AppConstant.uae_pass_login_type', target_hint='bss/uae_pass')
    shell = f('CustomTabControllerView', label='Authenticated tabs')
    link(email, shell, 'CustomTabControllerCoordinator(', 'bss/login/coordinator/login_coordinator', 'Successful full-access sign-in', 'state is LoginViaEmailSuccessState')
    link(otpemail, shell, 'CustomTabControllerCoordinator(', 'bss/email_otp_login/coordinator', 'Successful sign-in', 'state is LoginViaEmailSuccessState && state.response != null')
    mobileotp = f('OTPLoginScreen', label='Mobile number sign-in')
    link(login, mobileotp, 'OtpLoginCoordinator(', 'bss/login/presentation', 'Mobile number sign-in')
    link(mobileotp,shell,'CustomTabControllerCoordinator(', 'bss/otp_login/domain/bloc','Successful quick-access sign-in','OTP authenticated and login response saved; loginType == QUICK_ACCESS')
    otpscreen = fn(mobileotp, 'OTPScreen', 'OTPScreen(', 'bss/otp_login/coordinator', 'Verify mobile OTP', 'otpLoginStateStatus == OTPLoginStateStatus.otpSendQuickAccess && apiState == ApiState.success')
    fn(otpemail, 'OTPScreen', 'OTPScreen(', 'bss/email_otp_login/coordinator', 'Verify email OTP', 'otpLoginStateStatus == EmailOtpLoginStatus.otpSendQuickAccess')
    reg = fn(login, 'RegisterOnlineView', 'RegisterOnlineCoordinator(', 'bss/login/presentation/screens/main_login', 'Registration tab')
    reg_gate = b.decision('registration-config','BSS onboarding enabled?', 'commonData.bssOnboardingEnabled ?? true', [evidence('F','commonData.bssOnboardingEnabled ?? true','bss/login/presentation/widgets/login_screen_content')], notes='Null defaults to BSS. Register Now has an explicit native BAU alternative; the registration tab opens Flutter registration directly.')
    b.edge(login,reg_gate,'Register Now',[evidence('F','commonData.bssOnboardingEnabled ?? true','bss/login/presentation/widgets/login_screen_content')])
    b.edge(reg_gate,reg,'BSS registration',[evidence('F','RegisterOnlineCoordinator(','bss/login/presentation/widgets/login_screen_content')],condition='bssOnboardingEnabled ?? true')
    b.edge(reg_gate,reg,'Synchronous native handoff throws',[evidence('F','catch (e)','bss/login/presentation/widgets/login_screen_content')],condition='!bssOnboardingEnabled && synchronous exception',notes='The channel call is not awaited here; the catch is not an asynchronous native-failure fallback.')
    bau_a=a('RegistrationNavigationInfoMainActivity'); bau_i=i('RegistrationInfoVC')
    b.edge(reg_gate,bau_a,'BAU registration • Android',[evidence('F','openBauRegistrationFlow','bss/login/presentation/widgets/login_screen_content'),evidence('A','RegistrationNavigationInfoMainActivity::class.java','FlutterNavigationHandler')],condition='bssOnboardingEnabled == false && Android')
    b.edge(reg_gate,bau_i,'BAU registration • iOS',[evidence('F','openBauRegistrationFlow','bss/login/presentation/widgets/login_screen_content'),evidence('I','openNativeOnboardScreen(on: currentVC)','FlutterLinkable+Login'),evidence('I','RegistrationInfoWrapper* wrapper','CommonMethods')],condition='bssOnboardingEnabled == false && iOS')
    shop_gate=b.decision('guest-shop','Guest Shop tab enabled?', 'FeatureConfig.isShopTabEnabled', [evidence('F','FeatureConfig.isShopTabEnabled == false','bss/login/presentation/screens/main_login')], default=True)
    discover_gate=b.decision('guest-discover','Discover content enabled?', 'FeatureConfig.discoverInShopTabEnabled', [evidence('F','FeatureConfig.discoverInShopTabEnabled','bss/login/presentation/screens/main_login')], default=True)
    b.edge(login,shop_gate,'Guest tabs',[evidence('F','FeatureConfig.isShopTabEnabled == false','bss/login/presentation/screens/main_login')])
    b.edge(shop_gate,discover_gate,'Shop tab visible',[evidence('F','tabs: [LoginTab(loginVM: widget.viewModel), ShopTab(), MoreTab()]','bss/login/presentation/screens/main_login')], condition='isShopTabEnabled',default=True)
    discover = fn(discover_gate, 'DiscoverScreen', 'DiscoverCoordinator(', 'bss/login/presentation/screens/main_login', 'Browse as guest', 'FeatureConfig.discoverInShopTabEnabled == true')
    empty=b.special('empty-guest-tab','Empty Shop tab content','terminal',[evidence('F','return const SizedBox();','bss/login/presentation/screens/main_login')],notes='The Shop tab still exists when only discoverInShopTabEnabled is false; its content is SizedBox.')
    b.edge(discover_gate,empty,'Disabled content',[evidence('F','return const SizedBox();','bss/login/presentation/screens/main_login')],condition='!discoverInShopTabEnabled',default=False)
    no_shop=b.special('no-guest-shop','Login and More only','terminal',[evidence('F','AddTabEvent(tabs: [LoginTab(loginVM: widget.viewModel), MoreTab()])','bss/login/presentation/screens/main_login')])
    b.edge(shop_gate,no_shop,'Shop disabled',[evidence('F','FeatureConfig.isShopTabEnabled == false','bss/login/presentation/screens/main_login')],condition='!isShopTabEnabled',default=False)
    more = f('MoreMenuScreen', label='Guest More menu')
    link(login, more, 'MoreMenuScreen(', 'bss/login/presentation/screens/main_login', 'Guest More')
    service = b.service('uaepass', 'UAE PASS identity service', [evidence('F','getWebView(', 'bss/uae_pass')])
    b.edge(uaepass, service, 'Authenticate and return identity result', [evidence('F','getWebView(', 'bss/uae_pass')], kind='service')
    b.note('LoginCoordinator includes a Flutter SplashScreen readiness screen before MainLoginScreen. Native LoginViewController / LoginActivity source fallbacks are obsolete per product instruction.')

    b.journey('shell', 'Which tabs and dashboards does this user see?', 'Home & accounts',
              'Backend profile menus, active prepaid account, login type and role independently select the shell.')
    shell = f('CustomTabControllerView'); b.entry(shell)
    sp = declaration('F','CustomTabControllerView')
    sev = lambda needle: b.ev('F',sp,needle)
    menu = b.decision('menu', 'Profile menu loaded?', 'state is CustomTabControllerSuccessState / CustomTabControllerErrorState', [sev('state is CustomTabControllerSuccessState'),sev('state is CustomTabControllerErrorState')])
    b.edge(shell,menu,'Load backend profile menus',[sev('widget.vm.getProfileMenu();')])
    quick = b.decision('login-type','Quick access or full access?', 'widget.vm.input.loginType == LoginTypeConstants.QUICK_ACCESS', [sev('widget.vm.input.loginType == LoginTypeConstants.QUICK_ACCESS')])
    b.edge(menu,quick,'Menu available',[sev('_setupTabs(state);')],condition='CustomTabControllerSuccessState')
    admin = f('AdminDashboardScreen', label='Business Home')
    indiv = f('IndividualDashboardScreen',label='Individual Home')
    prepaid = f('PrepaidHomeScreen',label='Prepaid Home')
    homeproduct = b.decision('home-product','First linked account prepaid?', 'account.productCode == ProductCode.prePaidValue', [sev('account.productCode == ProductCode.prePaidValue')])
    b.edge(quick,admin,'Full access',[sev('return AdminDashboardScreen(')],condition='loginType != QUICK_ACCESS')
    b.edge(quick,homeproduct,'Quick access',[sev('tabs.add(HomeTab());')],condition='loginType == QUICK_ACCESS')
    b.edge(homeproduct,prepaid,'Prepaid',[sev('return PrepaidHomeScreen(')],condition='first linked account productCode == prePaidValue')
    b.edge(homeproduct,indiv,'Postpaid',[sev('return IndividualDashboardScreen(')],condition='first linked account productCode != prePaidValue')
    active = b.decision('active','Active prepaid account?', '_isPrepaidActiveAccount(): selectedAccount.productCode == prePaidValue; otherwise first account of first nonempty party', [sev('if (_isPrepaidActiveAccount())'),sev('commonData.selectedAccount?.productCode == ProductCode.prePaidValue')])
    b.edge(menu,active,'Choose remaining tabs',[sev('if (_isPrepaidActiveAccount())')],condition='profile menu success')
    support = f('SupportMenuScreen'); more = f('AuthenticatedMoreScreen')
    b.edge(active,support,'Support',[sev('return SupportMenuScreen(')],condition='always; prepaid branch returns after Support + More')
    b.edge(active,more,'More',[sev('return AuthenticatedMoreScreen(')],condition='always; prepaid branch omits Pay, Shop and Manage')
    paygate = b.decision('pay','Pay menu enabled?', 'menu.id == 11 && (menu.subMenu?.isNotEmpty ?? false) && !_isPrepaidActiveAccount()', [sev('bool payExists = menuList?.any(')])
    shopgate = b.decision('shop','Shop menu enabled?', 'menu.id == 3 && !_isPrepaidActiveAccount()', [sev('bool shopExists = menuList?.any(')])
    managegate = b.decision('manage','Manage menu enabled?', 'menu.id == 7 && (menu.subMenu?.isNotEmpty ?? false) && !_isPrepaidActiveAccount()',[sev('bool manageExists = menuList?.any(')])
    for gate in (paygate,shopgate,managegate): b.edge(active,gate,'Non-prepaid account',[sev('final usesBusinessDelegateManageTab')],condition='!_isPrepaidActiveAccount()')
    pay = f('AdminPayTabScreen'); ipay = f('IndividualPayScreen'); shop = f('ShopHomeScreen')
    b.edge(paygate,pay,'Full access Pay',[sev('return AdminPayTabScreen(')],condition='payExists && loginType != QUICK_ACCESS')
    b.edge(paygate,ipay,'Quick access Pay',[sev('return IndividualPayScreen(')],condition='payExists && loginType == QUICK_ACCESS')
    b.edge(shopgate,shop,'Shop',[sev('return ShopHomeScreen(')],condition='shopExists')
    role = b.decision('role','Business delegate role?', 'roles.trim().toUpperCase() intersects LEAD, BUSINESS_REPRESENTATIVE, CUSTOMER REPRESENTATIVE, CUSTOMER REPRESENTATIVE (DELEGATE)',[sev('_businessDelegateManageRoles'),sev('.any(_businessDelegateManageRoles.contains)')])
    b.edge(managegate,role,'Manage permitted',[sev('if (manageExists)')],condition='manageExists')
    am = f('AdminManageMenuScreen'); im = f('IndividualManageScreen')
    b.edge(role,am,'Delegate Manage',[sev('return AdminManageMenuScreen(')],condition='usesBusinessDelegateManageTab')
    b.edge(role,im,'Other roles',[sev('return IndividualManageScreen(')],condition='!usesBusinessDelegateManageTab; includes ACCOUNTANT and IT_MANAGER')
    fallback = b.decision('fallback','Profile menu request failed', 'CustomTabControllerErrorState', [sev('state is CustomTabControllerErrorState')])
    b.edge(menu,fallback,'Failure',[sev('state is CustomTabControllerErrorState')],condition='CustomTabControllerErrorState')
    for end,label,cond,needle in [(quick,'Home chosen by login type','QUICK_ACCESS → HomeTab; otherwise AdminDashboardTab','loginType == LoginTypeConstants.QUICK_ACCESS'),(support,'Support','menu request failed','SupportMenu('),(more,'More','menu request failed','MoreMenu(),')]:
        b.edge(fallback,end,label,[sev(needle)],condition=cond)
    b.note('The error shell contains only Home, Support and More. It still builds HomeTab for quick access, so prepaid Home may appear. No permission for Pay/Shop/Manage is inferred from failure.')

    b.journey('dashboard', 'Business Home, company accounts and account dashboards', 'Home & accounts')
    admin = f('AdminDashboardScreen'); b.entry(admin)
    ap = declaration('F','AdminDashboardScreen')
    legacygate = b.decision('legacy','Use legacy Home layout?', 'input.isLegacyDashboardEnabled && !input.isMigratedUser && input.ownerAcceptingRequestId.isEmpty',[b.ev('F',ap,'if (input.isLegacyDashboardEnabled'),b.ev('F',ap,'input.ownerAcceptingRequestId.isEmpty')],default=False,notes='Current FeatureConfig.isLegacyDashboardEnabled = false; the BAU layout remains a configured alternative.')
    b.edge(admin,legacygate,'Select Home layout',[b.ev('F',ap,'if (input.isLegacyDashboardEnabled')])
    legacy = f('AdminDashboardLegacyScreen'); body = f('AdminDashboardScreenBody',kind='content',label='Business Home content')
    b.edge(legacygate,legacy,'Legacy layout',[b.ev('F',ap,'return AdminDashboardLegacyScreen(')],condition='legacy predicate true',default=False)
    b.edge(legacygate,body,'Current layout',[b.ev('F',ap,'child: const AdminDashboardScreenBody()')],condition='legacy predicate false',default=True)
    party = fn(body,'PartyDashboardScreen','AppRoutes.partyDashboard', 'dashboard/admin', 'Select company / party')
    accounts = fn(party,'PartyIdAccountsSelectionScreen','AppRoutes.accountSelection', 'dashboard/party', 'View company accounts')
    product = b.decision('product','BFM account?', 'selected account productCode == ProductCode.bfm', [evidence('F',"account.productCode == 'BFM'",'dashboard/admin/views/widgets/admin_dashboard_screen_body')])
    for start in (body,party,accounts):
        # Corresponding pages call a shared account boundary or native account handoff.
        b.edge(start,product,'Select account',[evidence('F','ChannelController.openAccountDashboard(', 'dashboard/admin/views/widgets/admin_dashboard_screen_body')],notes='Dashboard, party and account selection use the same BFM/native account distinction; entry-specific callers retained in source inventory.')
    core = f('AccountCoreScreen'); ah = a('HomeActivity'); ih = i('HomeViewController')
    b.edge(product,core,'BFM account',[evidence('F','AppRoutes.accountDashboard', 'dashboard/admin')],condition='account.productCode == BFM')
    b.edge(product,ah,'Other account • Android',[evidence('F','ChannelController.openAccountDashboard(', 'dashboard/admin'), evidence('A','HomeActivity','FlutterNavigationHandler')],condition='productCode != BFM && platform == Android')
    b.edge(product,ih,'Other account • iOS',[evidence('F','ChannelController.openAccountDashboard(', 'dashboard/admin'), evidence('I','getHomeVCWith','FlutterLinkable')],condition='productCode != BFM && platform == iOS')
    overview = fn(core,'AccountOverviewScreen','AccountOverviewCoordinator(', 'dashboard/account/account_core', 'Overview tab')
    fn(core,'ContractDetailsScreen','ContractDetailsCoordinator(', 'dashboard/account/account_core', 'Contract tab')
    fn(core,'DashboardBillingWidget','BillingCoordinator(', 'dashboard/account/account_core', 'Billing tab',kind='content')
    sub = b.portal('subscriptions','BFM subscriptions and fixed addons','subscriptions',[evidence('F','SubscriptionsCoordinator(', 'dashboard/account/account_core')])
    b.edge(core,sub,'Subscriptions tab',[evidence('F','SubscriptionsCoordinator(', 'dashboard/account/account_core')])
    docs = fn(body,'ViewDocumentsScreen','ViewDocumentsCoordinator(', 'dashboard/admin', 'Company registration documents')
    acceptance = fn(body,'OwnerAcceptanceScreen','OwnerAcceptanceCoordinator(', 'dashboard/admin', 'Owner authorization request', 'ownerAcceptingRequestId is supplied and pending owner request is resolved')
    fn(acceptance,'AcceptanceDetailsScreen','AcceptanceDetailsScreen(', 'owner_acceptance', 'Review request details')
    companies = f('CompaniesScreen')
    link(body,companies,'CompaniesScreen(', 'dashboard/admin/views/widgets/admin_dashboard_success_widget','My companies', 'migrated user')
    b.note('Overview, contract, subscriptions and billing are Flutter tabs inside AccountCoreScreen, not independent native dashboards. Backend-loaded company/account eligibility remains authoritative.')

    b.journey('bfm-call-statistics','BFM call statistics and call history','Home & accounts')
    overview=f('AccountOverviewScreen'); b.entry(overview)
    stats=fn(overview,'CallStatisticsScreen','CallStatisticsCoordinator(', 'dashboard/account/account_overview','Call statistics')
    fn(stats,'CallHistoryScreen','CallHistoryCoordinator(', 'call_stats','View call history')

    b.journey('pay-tabs','Business Pay: configured old and new layouts','Billing & payment')
    pay=f('AdminPayTabScreen'); b.entry(pay)
    pp=declaration('F','AdminPayTabScreen')
    gate=b.decision('layout','Legacy Pay enabled?', 'input.isLegacyPayTabEnabled',[b.ev('F',pp,'input.isLegacyPayTabEnabled')],default=True,notes='Current FeatureConfig.isLegacyPayTabEnabled = true.')
    b.edge(pay,gate,'Choose layout',[b.ev('F',pp,'input.isLegacyPayTabEnabled')])
    old=f('AdminPayTabOldScreenBody',kind='content'); new=f('AdminPayTabScreenBody',kind='content')
    b.edge(gate,old,'Legacy layout',[b.ev('F',pp,'AdminPayTabOldScreenBody(')],condition='isLegacyPayTabEnabled',default=True)
    b.edge(gate,new,'New layout',[b.ev('F',pp,'AdminPayTabScreenBody(')],condition='!isLegacyPayTabEnabled',default=False)
    due=fn(new,'AdminTotalDueDetailsScreen','AdminTotalDueDetailsScreen(', 'admin_billing_and_payment/admin_pay_tab', 'Total due accounts')
    history=fn(new,'AdminBillingHistoryDetailsScreen','AdminBillingHistoryDetailsScreen(', 'admin_billing_and_payment/admin_pay_tab', 'Billing history')
    fn(history,'PdfFileView','PdfFileView(', 'admin_billing_and_payment/admin_billing_history_details','Download / view invoice')
    for call,asym,isym,label in [('openTotalDueDetails','BillsAndPaymentPayMyBillsActivity','PayMyBillsVC','Current total due'),('openBillingHistoryDetails','BillsAndPaymentAccountsActivity','BillsHistoryDetailVC','Billing accounts / history'),('openPayFlow','PaymentMainActivity','MakePaymentViewController','Pay now'),('openAutoPay','AutoPayMainActivity','AutoPayConfigureVC','Auto Pay'),('navigateToPaymentHistory','BillsAndPaymentPaymentHistoryActivity','PaymentHistoryVC','Payment history'),('openSummaryBill','SummaryBillMainActivity','SummaryBillGroupListViewController','Summary bills')]:
        ev=evidence('F',call,'admin_billing_and_payment/admin_pay_tab')
        for repo,sym in [('A',asym),('I',isym)]:
            dest=node(repo,sym)
            b.edge(old,dest,label+' • '+('Android' if repo=='A' else 'iOS'),[ev,evidence(repo,sym,'Flutter' if repo=='A' else '')],condition='platform == '+('Android' if repo=='A' else 'iOS'))
    gate=b.decision('bfm','Selected due account is BFM?', 'account.productCode == ProductCode.bfm',[evidence('F',"account.productCode == 'BFM'",'admin_billing_and_payment/admin_total_due')])
    b.edge(due,gate,'Select billing account',[evidence('F',"account.productCode == 'BFM'",'admin_billing_and_payment/admin_total_due')])
    bfm=f('DashboardBillingWidget',kind='content')
    b.edge(gate,bfm,'BFM billing',[evidence('F','BillingCoordinator(', 'admin_billing_and_payment/admin_total_due')],condition='BFM account')
    for repo,sym in [('A','BillsAndPaymentBillDetailsActivityNew'),('I','ViewBillOverviewVC')]:
        end=node(repo,sym)
        b.edge(gate,end,'Other product • '+repo,[evidence('F','openAccountBill','admin_billing_and_payment/admin_total_due')],condition='productCode != BFM && platform == '+repo)

    b.journey('individual-pay','Individual bills and invoice download','Billing & payment')
    ipay=f('IndividualPayScreen'); b.entry(ipay)
    success=f('IndividualPaySuccessWidget',kind='content')
    link(ipay,success,'IndividualPaySuccessWidget(', 'dashboard/individual_pay','Loaded bills')
    pdf=fn(ipay,'PdfFileView','PdfFileView(', 'dashboard/individual_pay/views/individual_pay_screen','Download / read / share invoice', 'downloadInvoiceState is success')
    for repo,sym in [('A','PaymentMainActivity'),('I','MakePaymentViewController')]:
        link(success,node(repo,sym),'openPayFlow','dashboard/individual_pay','Pay now • '+repo,'platform == '+repo)
    for repo,sym in [('A','BillsAndPaymentBillDetailsActivityNew'),('I','ViewBillOverviewVC')]:
        link(success,node(repo,sym),'openViewBillDetails','dashboard/individual_pay','Bill details • '+repo,'platform == '+repo)
    renderer=b.service('pdf','PDF render, save and share',[evidence('F','PdfFileView(', 'dashboard/individual_pay/views/individual_pay_screen')])
    b.edge(pdf,renderer,'Render / share file',[evidence('F','PdfFileView(', 'dashboard/individual_pay/views/individual_pay_screen')],kind='service')

    b.journey('bfm-billing','BFM invoices, credit limit and billing details','Billing & payment')
    billing=f('DashboardBillingWidget',kind='content'); b.entry(billing)
    bill=fn(billing,'ViewBillDetailsScreen','ViewBillDetailsCoordinator(', 'dashboard/account/billing','View current / historical bill', 'billing account and bill history are available')
    fn(billing,'UpdateCreditLimitScreen','UpdateCreditLimitCoordinator(', 'dashboard/account/billing','Update credit limit')
    fn(billing,'ChangeBillingDetailsScreen','ChangeBillingDetailsCoordinator(', 'dashboard/account/billing','Change billing details')
    methods=fn(billing,'PaymentMethodsScreen','PaymentMethodsCoordinator(', 'dashboard/account/billing','Pay outstanding balance', 'totalDueAmount > 0')
    fn(bill,'PdfFileView','PdfFileView(', 'view_bill_details','Download invoice')
    for repo,sym in [('A','PaymentMainActivity'),('I','MakePaymentViewController')]: link(bill,node(repo,sym),'openPayFlow','view_bill_details','Invoice-detail Pay • '+repo,'platform == '+repo)
    consent=fn(methods,'ConsentScreen','ConsentScreen(', 'payment_methods','Payment consent')
    result=fn(methods,'FlowResultScreen','FlowResultScreen(', 'payment_methods','Payment result')
    psdk=b.service('payment','Card / wallet provider execution',[evidence('F','ChannelController','payment_methods')])
    b.edge(methods,psdk,'Start payment SDK',[evidence('F','ChannelController','payment_methods')],kind='service')
    b.edge(psdk,result,'Payment callback',[evidence('F','FlowResultScreen(', 'payment_methods')],kind='return')

    b.journey('native-payment','Native payment portal, errors and completion','Billing & payment')
    an=native_internal('A',['PaymentMainActivity','PaymentPortalActivity','PaymentShowErrorActivity'])
    b.entry(an['PaymentMainActivity'])
    ins=native_internal('I',['MakePaymentViewController','CustomWebViewController','BillPaymentSuccessViewController','ViewPayBillsVC','ViewBillOverviewVC'])
    b.entry(ins['MakePaymentViewController'])
    for target,call,label in [('OrderDetailsScreen','navigateToOrderDetails(','Preorder continuation'),('OrdersListingScreen','navigateToOrderTracking(','Order tracking continuation')]:
        dest=f(target)
        ev=evidence('A',call,'payment/main/PaymentMainActivity')
        b.edge(an['PaymentMainActivity'],dest,label,[ev],kind='return',condition=('checkIsPreOrder() && orderResponse != null && referenceNumber != null' if target == 'OrderDetailsScreen' else 'Const.IS_NEW_ORDER_TRACKING; tap transaction id'),notes='Native payment success has branch-specific Flutter continuation; it does not always return to Flutter Home.')
    sdk=b.service('epg','Payment provider / wallet',[evidence('A','PaymentPortalActivity','payment/main/PaymentMainActivity')])
    b.edge(an['PaymentPortalActivity'],sdk,'Provider transaction',[evidence('A','PaymentPortalActivity','payment/main/PaymentMainActivity')],kind='service')

    b.journey('native-bills','Native bills, summary bills and payment history','Billing & payment')
    an=native_internal('A',['BillsAndPaymentMenuActivity','BillsAndPaymentPayMyBillsActivity','BillsAndPaymentViewAndPayBillsActivity','BillsAndPaymentAccountsActivity','BillsAndPaymentBillDetailsActivity','BillsAndPaymentBillDetailsActivityNew','BillsAndPaymentBillSummaryActivity','BillsAndPaymentPaymentHistoryActivity','BillsAndPaymentPaymentHistoryDetailsActivity','SummaryBillMainActivity','SummaryBillDetailsActivity','PaymentMainActivity'])
    b.entry(an['BillsAndPaymentMenuActivity'])
    ins=native_internal('I',['ViewPayBillsVC','PayMyBillsVC','BillsHistoryDetailVC','ViewBillOverviewVC','PaymentHistoryVC','SummaryBillGroupListViewController','SummaryBillDetailsViewController','BillDetailPDFViewController','MakePaymentViewController'])
    b.entry(ins['ViewPayBillsVC'])
    b.edge(ins['ViewPayBillsVC'],ins['MakePaymentViewController'],'Pay current balance',[evidence('I','pushToMakePaymentVC:self',declaration('I','ViewPayBillsVC').replace('.h','.m'))],condition='payment accounts / due amount available')
    menu_content=a('BillsPaymentNavFragment',kind='content',label='Native bills menu content')
    b.edge(an['BillsAndPaymentMenuActivity'],menu_content,'Bills menu',[evidence('A','BillsPaymentNavFragment()','BillsAndPaymentMenuActivity')])
    for target in ['BillsAndPaymentAccountsActivity','BillsAndPaymentPaymentHistoryActivity','SummaryBillMainActivity']:
        b.edge(menu_content,an[target],'Open '+friendly(target),[nav_evidence('A',target,declaration('A','BillsPaymentNavFragment'))],condition='Backend menu item / selected billing history')
    # The Flutter Pay tab is a proved entry for all these native subflows.
    pay_entry=f('AdminPayTabOldScreenBody',kind='content'); b.entry(pay_entry)
    for repo,targets in [('A',['BillsAndPaymentPayMyBillsActivity','BillsAndPaymentAccountsActivity','BillsAndPaymentPaymentHistoryActivity','SummaryBillMainActivity']),('I',['PayMyBillsVC','BillsHistoryDetailVC','PaymentHistoryVC','SummaryBillGroupListViewController'])]:
        mapping=an if repo=='A' else ins
        for target in targets:
            call='openTotalDueDetails' if target in ('BillsAndPaymentPayMyBillsActivity','PayMyBillsVC') else 'openBillingHistoryDetails' if target in ('BillsAndPaymentAccountsActivity','BillsHistoryDetailVC') else 'navigateToPaymentHistory' if 'PaymentHistory' in target else 'openSummaryBill'
            b.edge(pay_entry,mapping[target],friendly(target),[evidence('F',call,'admin_pay_tab/views/widgets/old')],condition='platform == '+repo)
    # Native bills menu data handler owns these iOS row transitions.
    for target in ['PaymentHistoryVC','BillsHistoryDetailVC','SummaryBillGroupListViewController']:
        b.edge(ins['ViewPayBillsVC'],ins[target],'Selected billing menu row',[evidence('I',target,'ViewPayBillsDataHandler.m')],condition='row cellTag selects destination')
    # Existing native side-menu / notification / bad-debt paths also enter bills.
    native_external=b.special('native-entry','Native notification, side-menu or bad-debt entry','entry',[evidence('A','BillsAndPaymentViewAndPayBillsActivity::class.java','FlutterNavigationHandler')],notes='Retained native flow entry, separate from the Flutter Pay tab.')
    b.entry(native_external)
    b.edge(native_external,an['BillsAndPaymentViewAndPayBillsActivity'],'Billing menu after native handoff',[evidence('A','BillsAndPaymentViewAndPayBillsActivity::class.java','FlutterNavigationHandler')])
    b.edge(native_external,an['BillsAndPaymentBillDetailsActivity'],'Native side-menu account invoice',[evidence('A','BillsAndPaymentBillDetailsActivity.class','sidemenu/SideMenuActivity')],condition='native account-specific bills entry')
    b.note('Native billing also uses fragments/list row handlers. Missing direct screen-to-screen constructor references are not invented here; the inventory preserves caller evidence for those intermediate components.')

    b.journey('autopay','Auto Pay setup, management and provider results','Billing & payment')
    an=native_internal('A',['AutoPayMainActivity','AutoPaySetupActivity','AutoPayPaymentSetupActivity','AutoPayTermsAndCondsActivity','AutopayManageActivity','AutopayDetailsActivity','AutopayManagePaymentActivity','AutopayEPGPortalActivity'])
    b.entry(an['AutoPayMainActivity'])
    ins=native_internal('I',['AutoPayConfigureVC','AutoPayViewController','AutoPaySetupAccountsDetailsVC','AutoPayViewAccountDetailsVC','AutoPayRemoveCardAlertVC','AutoPayFilterViewController','AutoPayUpdateCardsVC','CustomWebViewController','AutoPaySuccessMessageVC'])
    b.entry(ins['AutoPayConfigureVC'])

    b.journey('prepaid-recharge','Prepaid Home and native recharge','Billing & payment')
    home=f('PrepaidHomeScreen'); b.entry(home)
    an=native_internal('A',['EasyPrepaidRechargeActivity','EasyPrepaidPaymentActivity','EasyPrepaidVoucherOrCardRechargeActivity','EasyPrepaidQrScanningActivity','PaymentPortalActivity','EasyPrepaidMainActivity','EasyPrepaidAboutActivity'])
    link(home,an['EasyPrepaidRechargeActivity'],'openEasyPrepaidRecharge','dashboard/prepaid_home','Recharge • Android','platform == Android')
    vendor=b.unresolved('ios-recharge','iOS prepaid recharge screen',[evidence('I','navigateToPrePaidRechargeVC','FlutterLinkable')],notes='Concrete controller selected behind commonMethodsVendor; do not infer a Flutter destination from the bridge.')
    link(home,vendor,'openEasyPrepaidRecharge','dashboard/prepaid_home','Recharge • iOS','platform == iOS')
    b.note('Android completion explicitly opens EasyPrepaidMainActivity, the native prepaid Home. It does not automatically return to Flutter PrepaidHomeScreen.')

    b.journey('registration','Registration: identity, emirate and company method','Login & registration')
    reg=f('RegisterOnlineView'); b.entry(reg)
    up=fn(reg,'UaePassScreen','UaePassCoordinator(', 'registration/common/register_online/viewmodel','Authenticate UAE PASS',target_hint='bss/uae_pass')
    sharing=fn(reg,'UaePassDocumentSharingScreen','UaePassCoordinator(', 'registration/common/register_online/bloc','Share identity documents',target_hint='bss/uae_pass')
    contact=fn(sharing,'OnboardingUserDetailsScreen','OnboardingUserDetailsCoordinator(', 'registration/common/register_online/bloc','Validate contact details', 'successful document sharing; !isSelfUpgrade')
    emirate=fn(contact,'EmirateSelectionScreen','EmirateSelectionCoordinator(', 'registration/common/register_online/bloc','Select company emirate', 'onComplete returns email/mobile verification tokens')
    opts=fn(emirate,'EmirateOptionsScreen','EmirateOptionsScreen(', 'registration/common/emirate_selection','Select available registration method', 'item.childValues is not empty')
    gate=b.decision('method','Registration method from emirate configuration', "handleOptions switch(option): DUL / MOE / default",[evidence('F','switch (option)', 'registration/common/register_online/bloc')])
    b.edge(opts,gate,'Selected option',[evidence('F','handleOptions(', 'registration/common/register_online/bloc')])
    dul=fn(gate,'CustomerDetailsView','CustomerDetailsCoordinator(', 'registration/common/register_online/bloc','Digital trade license (DUL)', "option == 'DUL'")
    ner=fn(gate,'NerScreen','NerCoordinator(', 'registration/common/register_online/bloc','National economic register (NER)', "option == 'MOE'")
    manual=fn(gate,'ManualUploadScreen','ManualUploadCoordinator(', 'registration/common/register_online/bloc','Manual document upload', "option is neither 'DUL' nor 'MOE'; also isSelfUpgrade")
    fn(reg,'BlackListedScreen','BlackListedScreen(', 'registration/common/register_online/bloc','Identity blocked', 'backend reports blacklisted identity',target_hint='bss/signup')
    b.note('The initial registration branch uses MOE for NER; renewal RegistrationOptionsView uses NER. These backend option codes are preserved separately.')

    b.journey('registration-dul','DUL lookup, account review and OTP','Login & registration')
    customer=f('CustomerDetailsView'); b.entry(customer)
    fetch=fn(customer,'FetchInformationView','FetchInformationCoordinator(', 'registration/dul/customer_details','Fetch trade license information')
    timer=fn(fetch,'LoadingTimerView','LoadingTimerCoordinator(', 'registration/dul/fetch_information','Wait for DUL response')
    summary=fn(customer,'AccountSummaryView','AccountSummaryCoordinator(', 'registration/dul/customer_details','Review returned accounts', 'DUL information access completes')
    contact=fn(summary,'ConfirmContactDetailsView','ConfirmContactDetailsCoordinator(', 'registration/dul/account_summary','Confirm contacts')
    otp=fn(contact,'OTPVerificationView','OTPVerificationCoordinator(', 'registration/common/confirm_contact_details','Verify contact OTP')
    fn(otp,'DULOTPSuccessScreen','DULOTPSuccessScreen(', 'registration/common/otp_verification','Registration submitted', 'API contact verification success')
    fn(fetch,'DULPendingRequestScreen','DULPendingRequestScreen(', 'registration/dul/fetch_information/bloc','Pending DUL request', 'backend request status is pending')
    fail=fn(timer,'TwoActionsSuccessScreen','TwoActionsSuccessScreen(', 'registration/dul/loading_timer/bloc','DUL unavailable / retry or manual', 'DUL polling failure / timeout')
    fn(fail,'ManualUploadScreen','ManualUploadCoordinator(', 'registration/dul/loading_timer/bloc','Continue with manual documents')
    fn(fail,'RegisterOnlineView','RegisterOnlineCoordinator(', 'registration/dul/loading_timer/bloc','Restart registration')

    b.journey('registration-manual','Manual registration and alternate authorization','Login & registration')
    manual=f('ManualUploadScreen'); b.entry(manual)
    upload=fn(manual,'UploadDocumentScreen','UploadDocumentCoordinator(', 'registration/manual_upload/presentation','Upload requested company document', 'ManualUploadStatus.uploadTL / requested document stage')
    face=fn(manual,'FaceRecognitionScreen','FaceRecognitionCoordinator(', 'registration/manual_upload/presentation','Verify face', 'ManualUploadStatus.faceVerification')
    approval=fn(manual,'ApprovalFlowScreen','ApprovalFlowCoordinator(', 'registration/manual_upload/presentation','Owner approval', 'face verification matches')
    fn(manual,'PendingAuthorizationScreen','PendingAuthorizationScreen(', 'registration/manual_upload/presentation','Authorization pending', 'state.status == ManualUploadStatus.pendingAuthorization')
    fn(manual,'DetailsScreen','DetailsScreen(', 'registration/manual_upload/presentation','Review uploaded details')
    fn(manual,'PendingRequestsWarningScreen','PendingRequestsWarningScreen(', 'registration/manual_upload/domain/bloc','Existing pending request', 'backend reports prior pending request',target_hint='registration/manual_upload')
    method=fn(approval,'OnboardingSelectAuthMethodScreen','OnboardingSelectAuthMethodCoordinator(', 'registration/approval_flow','Choose authorization method', 'state.status == ApprovalFlowStatus.selectAuthMethod')
    fn(approval,'OwnerEmailConfirmation','OwnerEmailConfirmation(', 'registration/approval_flow','Confirm owner email', 'alternate owner authorization branch')
    fn(approval,'UploadDocumentScreen','UploadDocumentCoordinator(', 'registration/approval_flow','Upload authorization document', 'requested approval stage')
    fn(approval,'FaceRecognitionScreen','FaceRecognitionCoordinator(', 'registration/approval_flow','Owner face verification', 'requested approval stage')
    fn(approval,'SuccessUserScreen','SuccessUserCoordinator(', 'registration/approval_flow','Approval result')
    fn(manual,'SuccessUserScreen','SuccessUserCoordinator(', 'registration/manual_upload/presentation','Registration result')
    sdk=b.service('efr','EFR liveness and face-match SDK',[evidence('F','EFRService','bss/face_recognition')])
    b.edge(face,sdk,'Capture and verify face',[evidence('F','EFRService','bss/face_recognition')],kind='service')
    b.edge(sdk,manual,'Verification callback',[evidence('F','FaceRecognitionCoordinator(', 'registration/manual_upload/presentation')],kind='return')

    b.journey('registration-tracking','Track registration and verify status','Login & registration')
    login=f('RegisterOnlineView'); b.entry(login)
    track=fn(login,'MainTrackScreen','TrackRegistrationCoordinator(', 'registration/common/register_online/viewmodel','Track registration')
    otp=fn(track,'OtpTrackRegistrationScreen','OtpTrackRegistrationCoordinator(', 'bss/track_registration/presentation','Verify tracking OTP')
    timeline=fn(otp,'TrackRegistrationTimelineScreen','TrackRegistrationTimelineCoordinator(', 'bss/otp_track_registration','View registration timeline')
    fn(timeline,'RegisterOnlineView','RegisterOnlineCoordinator(', 'bss/track_registration_timeline','Restart or amend registration')

    b.journey('authorization-renewal','Expired authorization, owner renewal and delegate LOA','Identity & users')
    login=f('MainLoginScreen'); b.entry(login)
    expired=f('AuthorizationExpiredScreen'); delegate=f('DelegateLoaRenewalCoordinatorScreen')
    link(login,expired,'AuthorizationExpiredScreen(', 'bss/login/coordinator','Authorization expired','!FlowDataModel().isDigitalLOAFlow')
    link(login,delegate,'DelegateLoaRenewalCoordinatorScreen(', 'bss/login/coordinator','Renew digital LOA','FlowDataModel().isDigitalLOAFlow && isUAEPassLogin')
    fn(login,'NotUaepassBottomSheetWidget','NotUaepassBottomSheetWidget(', 'bss/login/coordinator','Sign in with UAE PASS first','digital LOA flow && !isUAEPassLogin',kind='sheet')
    renewal=fn(expired,'OwnerAuthRenewalScreen','OwnerAuthRenewalCoordinator(', 'bss/login/presentation/screens/authorization_expired','Renew owner authority')
    fn(renewal,'CustomerIdMismatchScreen','CustomerIdMismatchScreen(', 'bss/owner_auth_renewal','Identity does not match')
    fn(renewal,'OwnerAuthRenewalErrorScreen','OwnerAuthRenewalErrorScreen(', 'bss/owner_auth_renewal','Renewal error')
    up=fn(renewal,'UaePassScreen','UaePassCoordinator(', 'bss/owner_auth_renewal/domain/viewmodel','Authenticate identity',target_hint='bss/uae_pass')
    options=fn(renewal,'RegistrationOptionsView','RegistrationOptionsCoordinator(', 'bss/owner_auth_renewal/domain/viewmodel','Choose renewal method')
    company=fn(renewal,'CompanyDetailsView','CompanyDetailsCoordinator(', 'bss/owner_auth_renewal/domain/viewmodel','Review company trade license',target_hint='re_registration_dul_ner')
    fn(company,'CompanyTradeLicenseChangeView','CompanyTradeLicenseChangeCoordinator(', 're_registration_dul_ner/company_details','Change trade license')
    fn(renewal,'RegistrationMobileAccountsView','RegistrationMobileAccountsCoordinator(', 'bss/owner_auth_renewal/domain/viewmodel','Review mobile accounts')
    fn(renewal,'UploadDocumentCoordinatorScreen','UploadDocumentCoordinatorScreen(', 'bss/owner_auth_renewal','Upload renewal document')
    fn(options,'CustomerDetailsView','CustomerDetailsCoordinator(', 'registration/common/registration_options','DUL renewal', "registrationOption.key == 'DUL' && input.isRegistration")
    fn(options,'NerScreen','NerCoordinator(', 'registration/common/registration_options','NER renewal', "registrationOption.key == 'NER' && input.isRegistration")
    fn(options,'ManualUploadScreen','ManualUploadCoordinator(', 'registration/common/registration_options','Manual renewal', "registrationOption.key == 'EFR' && input.isRegistration")
    dbody=fn(delegate,'DelegateLoaRenewalScreen','DelegateLoaRenewalScreen(', 'bss/delegate_loa_renewal/coordinator','Review digital LOA renewal')
    fn(dbody,'RenewalPendingRequestScreen','RenewalPendingRequestScreen(', 'bss/delegate_loa_renewal/coordinator','Renewal pending')
    fn(dbody,'SuccessUserScreen','SuccessUserCoordinator(', 'bss/delegate_loa_renewal/coordinator','Renewal submitted')
    b.note('RegistrationOptionsView in owner renewal is a selection callback when !input.isRegistration; the callback orchestrates fetch information, company details and loading. It is not a mandatory second registration.')

    b.journey('companies','My companies: portal or native renewal','Identity & users')
    manage=f('AdminManageMenuScreen'); b.entry(manage)
    migrated=b.decision('migrated','Migrated/BSS account context?', 'loggedInUser.migrated != null && netCrackerId != null && netcrackerJWToken != null',[evidence('F','if (!successState.isMigratedUser)', 'manage/admin_manage_menu/views')])
    b.edge(manage,migrated,'My companies menu',[evidence('F','ManageMenuMainMenuType.myCompanies','manage/admin_manage_menu/views')])
    portal=f('CompaniesScreen',label='My companies portal (Flutter webview)')
    b.edge(migrated,portal,'Migrated',[evidence('F','CompaniesScreen(', 'manage/admin_manage_menu/views')],condition='isMigratedUser')
    for repo,sym in [('A','ReRegisterMyCompaniesActivity'),('I','ReRegistrationRenewalVC')]:
        dest=node(repo,sym)
        b.edge(migrated,dest,'Non-migrated • '+repo,[evidence('F','openMyCompaniesFlowNative','manage/admin_manage_menu/views'),evidence(repo,sym,'Flutter' if repo=='A' else 'ReRegistrationRenewalCoordinator')],condition='!isMigratedUser && platform == '+repo)
    renewal=f('OwnerAuthRenewalCoordinatorScreen')
    b.edge(portal,renewal,'Renew trade license / establishment card / general documents',[evidence('F','OwnerAuthRenewalCoordinatorScreen(', 'bss/track_order/companies_screen')],condition='Portal action TL_Renewal / EC_Renewal / GD_Renewal; UAE PASS login prerequisite')
    b.note('Portal-owned remote pages and backend JavaScript actions are not locally enumerable; CompaniesScreen stays Flutter because Flutter owns its WebView route.')
    an=native_internal('A',['ReRegisterMyCompaniesActivity','ReRegisterMyCompaniesDetailsActivity','RegistrationRenewalStatusActivity'])
    ins=native_internal('I',['ReRegistrationRenewalVC','ReRegistrationRenewalDetailVC','ReRegistrationAccountsVC','RegistrationStatusDetailsVC'])

    b.journey('users','Users and admins: migration and eligibility','Identity & users')
    manage=f('AdminManageMenuScreen'); b.entry(manage)
    gate=b.decision('mode','Migrated and authorized for user management?', "isMigratedUser; ncRole contains Customer Representative / Business Representative / Customer Representative (Delegate)",[evidence('F','if (!successState.isMigratedUser)','manage/admin_manage_menu/views'),evidence('F',"roles.contains('Customer Representative')",'manage/admin_manage_menu/bloc/admin_manage_menu_state')])
    b.edge(manage,gate,'Users and admins',[evidence('F','ManageMenuMainMenuType.userAndAdmin','manage/admin_manage_menu/views')])
    users=f('UsersListScreen')
    b.edge(gate,users,'BSS authorized',[evidence('F','if (successState.isEligibleForUserManagement)','manage/admin_manage_menu/views'),evidence('F','return UserManagementCoordinator(', 'manage/admin_manage_menu/views'),evidence('F','return UsersListScreen(', 'bss/user_management/coordinator')],condition='isMigratedUser && isEligibleForUserManagement')
    denied=b.unresolved('denied','Not authorized: message; no screen opened',[evidence('F','You are not authorized to see users','manage/admin_manage_menu/views')],notes='Concrete snackbar branch; this is not a missing target.')
    b.edge(gate,denied,'BSS without eligible ncRole',[evidence('F','You are not authorized to see users','manage/admin_manage_menu/views')],condition='isMigratedUser && !isEligibleForUserManagement')
    for repo,sym in [('A','UserManagementEmployeesActivity'),('I','UserAdminManagementVC')]:
        b.edge(gate,node(repo,sym),'BAU users • '+repo,[evidence('F','openUsersAndAdminsFlow','manage/admin_manage_menu/views'),evidence(repo,sym,'Flutter' if repo=='A' else 'UserAdminManagementCoordinator')],condition='!isMigratedUser && platform == '+repo)
    details=fn(users,'UserDetailsScreen','UserDetailsCoordinator(', 'bss/user_management/domain/view_model','Selected company-role user',target_hint='bss/user_details')
    role=fn(users,'RoleSelectionScreen','RoleSelectionCoordinator(', 'bss/user_management/domain/view_model','Add company-role user')
    add=fn(role,'AddUserScreen','AddUserCoordinator(', 'bss/add_user/presentation/screens/role_selection','Enter user details', 'selected role is not self-upgrade / Business Representative')
    fn(role,'SelfUpgradeScreen','SelfUpgradeCoordinator(', 'bss/add_user/presentation/screens/role_selection','Upgrade own role', 'self upgrade branch')
    fn(role,'StepsScreen','BusinessRepresentativeCoordinator(', 'bss/add_user/presentation/screens/role_selection','Add Business Representative', 'Business Representative branch',target_hint='bss/business_representative')
    fn(add,'SuccessUserScreen','SuccessUserCoordinator(', 'bss/add_user/domain/bloc','User added / updated', 'API submission success')
    fn(add,'UserAlreadyExistsScreen','UserAlreadyExistsScreen(', 'bss/add_user/domain/bloc','User already exists', 'backend existing-user response')
    fn(details,'CompanySelectionScreen','CompanySelectionCoordinator(', 'bss/user_details/presentation/widgets','Select company / add role')
    contact=fn(details,'BssUpdateContactCoordinatorScreen','BssUpdateContactCoordinatorScreen(', 'bss/user_details/presentation/widgets','Update user contact')
    contact_body=fn(contact,'BssUpdateContactScreen','BssUpdateContactScreen(', 'bss/update_contact/coordinator','Edit contact details')
    fn(contact_body,'DoubleOTPVerificationScreen','DoubleOTPVerificationScreen(', 'bss/update_contact','Verify changed contacts',target_hint='bss/update_contact')
    renewal=fn(details,'OwnerAuthRenewalScreen','OwnerAuthRenewalCoordinator(', 'bss/user_details/presentation/widgets','Renew expired authorization')
    b.note('Shell role eligibility and this user-management ncRole check are separate predicates. LEAD selecting business Manage does not automatically authorize the migrated users list.')

    b.journey('employees','Add, update or delete employees','Identity & users')
    users=f('UsersListScreen'); b.entry(users)
    choose=fn(users,'IndividualOrBulkUserScreen','AddEmployeesCoordinator(', 'bss/user_management/domain/view_model','Add employees')
    single=fn(choose,'LegacyAddEmployeeScreen','LegacyAddEmployeeScreen(', 'bss/add_employee/presentation/pages/individual_or_bulk_user','Add one employee', 'individual selection')
    bulk=fn(choose,'AddBulkEmployees','AddBulkEmployees(', 'bss/add_employee/presentation/pages/individual_or_bulk_user','Bulk file upload', 'bulk selection')
    success=fn(single,'AddEmployeeSuccessScreen','AddEmployeeSuccessScreen(', 'bss/add_employee/presentation/pages/legacy_add_employee','Employee saved', 'API add/update success',target_hint='bss/add_employee')
    fn(bulk,'AddEmployeeSuccessScreen','AddEmployeeSuccessScreen(', 'bss/add_employee/coordinator','Bulk submission result',target_hint='bss/add_employee')
    details=fn(users,'LegacyEmployeeDetailsScreen','LegacyEmployeeDetailsScreen(', 'bss/user_management/domain/view_model','View employee')
    fn(details,'LegacyAddEmployeeScreen','LegacyAddEmployeeScreen(', 'bss/user_management/presentation/widgets/bottom_sheets','Update employee')
    fn(users,'DeleteEmployeeSuccessScreen','DeleteEmployeeSuccessScreen(', 'bss/user_management/domain/bloc','Employee deleted', 'confirmed deletion and API success')
    picker=b.service('file','File picker / upload',[evidence('F','ChannelController','bss/add_employee/domain/viewModel')])
    b.edge(bulk,picker,'Choose employee spreadsheet',[evidence('F','ChannelController','bss/add_employee/domain/viewModel')],kind='service')

    b.journey('native-users','BAU employee management and invitation acceptance','Identity & users')
    an=native_internal('A',['UserManagementEmployeesActivity','UserManagementEmployeeDetailActivity','UserManagementAddEmployeeActivity','UserManagementUpdateEmployeeActivity','UserManagementTermsAndConditionActivityAdmin','UserManagementTermsAndConditionActivityBR','UserManagementUserNewDetailsActivityBR','UserManagementSuccessActivityAdmin','UserManagementSuccessActivityBR','SecurityCodeActivity','UserManagementSuccessUserAddActivity','UserManagementSuccessUserUpdateActivity','UserManagementErrorAlreadyExistsActivity','UserManagementErrorExpiredAuthorizationActivity','UserManagementErrorGenericActivity','UserManagementDeeplinkInviteActivity','UserManagementErrorDeepLinkErrorActivity','UserManagementErrorUaePassActivity','UserManagementUaePassDocumentSignInActivity','UserManagementOpenUaePassActivity'])
    b.entry(an['UserManagementEmployeesActivity']); b.entry(an['UserManagementDeeplinkInviteActivity'])
    employees_content=a('UserManagementEmployeesFragment',kind='content')
    b.edge(an['UserManagementEmployeesActivity'],employees_content,'Employees / administrators tabs',[evidence('A','UserManagementViewPagerAdapter(','UserManagementEmployeesActivity'),evidence('A','UserManagementEmployeesFragment.newInstance','UserManagementViewPagerAdapter')])
    for target in ['UserManagementAddEmployeeActivity','UserManagementEmployeeDetailActivity']:
        b.edge(employees_content,an[target],'Add employee' if 'AddEmployee' in target else 'Selected employee',[nav_evidence('A',target,declaration('A','UserManagementEmployeesFragment'))])
    security=a('SecurityCodeEmailActivity'); b.entry(security)
    b.edge(security,an['UserManagementUaePassDocumentSignInActivity'],'Verify invited user identity',[nav_evidence('A','UserManagementUaePassDocumentSignInActivity',declaration('A','SecurityCodeEmailActivity'))],condition='registration / invitation verification continuation')
    new_error=a('RegistrationUaePassNewErrorActivity')
    b.edge(an['UserManagementOpenUaePassActivity'],new_error,'UAE PASS identity error',[nav_evidence('A','RegistrationUaePassNewErrorActivity',declaration('A','UserManagementOpenUaePassActivity'))])
    ins=native_internal('I',['UserAdminManagementVC','AddUserVC','UserManagementDetailVC','ReviewVC','UserValidationVC','VerifyAccountVC','ConfirmationBottomSheetVC','DeleteUserBottomSheetVC'])
    b.entry(ins['UserAdminManagementVC'])
    ios_invite=b.special('ios-invite','iOS invitation URL entry','entry',[evidence('I','UserValidationWrapper()','URLTypes.swift')],notes='Current native URLTypes invitation handler; current login still Flutter.')
    b.entry(ios_invite)
    b.edge(ios_invite,ins['UserValidationVC'],'Accept / validate invited user',[evidence('I','UserValidationWrapper()','URLTypes.swift'),evidence('I','UserValidationVC.instanceFromStoryboard','UserValidationCoordinator')])

    b.journey('more-profile','More, user profile and password security','Profile & settings')
    more=f('AuthenticatedMoreScreen'); b.entry(more)
    success=f('AuthenticatedMoreSuccessWidget',kind='content')
    link(more,success,'AuthenticatedMoreSuccessWidget(', 'authenticated_more/views/widgets','More menu content')
    profile=fn(success,'UserProfileScreen','UserProfileCoordinator(', 'authenticated_more/views/widgets','BSS profile', 'input.isBssUser')
    legacy=fn(success,'ProfileDetailsScreen','ProfileDetailsCoordinator(', 'authenticated_more/views/widgets','BAU profile', '!input.isBssUser')
    forget=fn(success,'ForgetPasswordScreen','ForgetPasswordCoordinator(', 'authenticated_more/views/widgets','Change BSS password', 'input.isBssUser')
    fn(more,'ChangePasswordScreen','ChangePasswordCoordinator(', 'authenticated_more/views/authenticated_more_screen','Change BAU password', '!input.isBssUser; static content loaded')
    fn(profile,'ForgetPasswordScreen','ForgetPasswordCoordinator(', 'bss/user_details/presentation/screens/user_profile','Change password')
    terms=fn(success,'AppLanguageSheetContent','AppLanguageSheetContent(', 'authenticated_more/views/widgets','Language selection',kind='sheet')
    fn(success,'AuthenticatedMoreSecuritySheetWidget','AuthenticatedMoreSecuritySheetWidget(', 'authenticated_more/views/widgets','Security options',kind='sheet')
    fn(success,'PrepaidHomeScreen','PrepaidHomeScreen(', 'authenticated_more/views/widgets','Selected prepaid account Home')
    logout=b.service('logout','Clear session and logout',[evidence('F','ChannelController.logout(', 'authenticated_more/views/widgets')])
    b.edge(success,logout,'Confirm logout',[evidence('F','ChannelController.logout(', 'authenticated_more/views/widgets')],kind='service')
    b.journey('edit-profile-inbound','Edit profile inbound route (producer unconfirmed)','Profile & settings')
    boundary=b.unresolved('profile-entry','Registered profileManagementCM entry',[evidence('F','EditProfileCoordinator(','core/routes/native_navigation/profile_management_cm')],notes='Registered target is implemented; current incoming producer has not been established. ProfileDetailsScreen edit controls are commented out.')
    b.entry(boundary)
    edit=fn(boundary,'EditProfileScreen','EditProfileCoordinator(', 'core/routes/native_navigation/profile_management_cm','Edit profile when channel is invoked')
    fn(edit,'EmiratesIdDetailsScreen','EmiratesIdDetailsCoordinator(', 'edit_profile/coordinator','View Emirates ID')

    b.journey('password-reset','Flutter BSS password reset and OTP','Profile & settings')
    email=f('EmailLoginScreen'); b.entry(email)
    forget=fn(email,'ForgetPasswordScreen','ForgetPasswordCoordinator(', 'bss/login/presentation/widgets/email_login','Forgot password')
    otp=fn(forget,'OTPScreen','OTPScreen(', 'bss/forget_password/coordinator','Verify OTP', 'OTP sent')
    reset=fn(otp,'ResetPasswordScreen','ResetPasswordScreen(', 'bss/forget_password/coordinator','Set new password', 'OTP verified')
    fn(reset,'SuccessScreen','SuccessScreen(', 'bss/forget_password/coordinator','Password updated', 'reset success',target_hint='domain_activation_management/success')

    b.journey('native-registration-documents','BAU registration: manual documents and verification','Login & registration',
              'Reached from Flutter Register Now when BSS onboarding is disabled; native document order changes by role and renewal context.')
    an=native_internal('A',['RegistrationNavigationInfoMainActivity','RegistrationMainActivity','RegistrationStatusActivity','RegistrationTradeLicenseActivity','RegistrationEstablishmentActivity','RegistrationPowerOfAttorneyActivity','RegistrationEmiratesMainActivity','RegistrationEmiratesFrontActivity','RegistrationEmiratesBackActivity','RegistrationEmiratesModifyDataActivity','RegistrationPersonalDetailsActivity','RegistrationMobileNumberActivity','SecurityCodeActivity','SecurityCodeEmailActivity','RegistrationSuccessWithoutUaePassActivity'])
    b.entry(an['RegistrationNavigationInfoMainActivity'])
    data_path='app/src/main/java/ae/etisalat/smb/presentation/registration/RegistrationDataObject.kt'
    dispatcher=b.decision('documents','Which documents / role must be verified?', 'RegistrationDataObject requestType, hasTLInformation, hasEstablishmentCardInformation, hasEmiratesIDInformation, role', [b.ev('A',data_path,'RegistrationTradeLicenseActivity::class.java')],notes='Native state selects, skips and reorders document steps. These are alternatives, not a compulsory single chain.')
    # RegistrationMainActivity delegates subsequent routing through RegistrationDataObject.
    b.edge(an['RegistrationMainActivity'],dispatcher,'Continue registration',[evidence('A','RegistrationDataObject','registration/self_registration/RegistrationMainActivity')])
    for sym in ['RegistrationTradeLicenseActivity','RegistrationEstablishmentActivity','RegistrationPowerOfAttorneyActivity','RegistrationEmiratesMainActivity','RegistrationPersonalDetailsActivity','RegistrationMobileNumberActivity']:
        try: ev=b.ev('A',data_path,sym+'::class.java')
        except ValueError: continue
        b.edge(dispatcher,an[sym],'Required '+friendly(sym),[ev],condition='RegistrationDataObject role/document status selects this step')
    b.edge(an['RegistrationPersonalDetailsActivity'],an['RegistrationMobileNumberActivity'],'Personal details validated',[evidence('A','RegistrationMobileNumberActivity','RegistrationPersonalDetailsViewModel')])
    for origin in ['RegistrationTradeLicenseActivity','RegistrationEstablishmentActivity','RegistrationEmiratesMainActivity','RegistrationEmiratesModifyDataActivity','RegistrationPowerOfAttorneyActivity']:
        for target,cond in [('RegistrationSuccessWithoutUaePassActivity','!(RegistrationDataObject.isAuthorized == true || RegistrationDataObject.isEfrFlow)'),('RegistrationSuccessWithUaePassActivity','RegistrationDataObject.isAuthorized == true || RegistrationDataObject.isEfrFlow'),('RegistrationUaePassSubmitErrorActivity','mResponseCode == CODE_REGISTRATION_UAE_PASS_FETCH_DOCS_ERROR')]:
            end=a(target)
            b.edge(an[origin],end,'Registration submit result',[evidence('A','handleRegistrationSubmitResponse(',declaration('A',origin)),evidence('A',target+'::class.java','core/utils/ExtensionsView')],condition=cond)
    b.note('Identity scanning and SDK capture are platform capabilities. Manual registration screen branches remain native UI; native login is excluded.')

    b.journey('native-registration-uaepass','BAU UAE PASS, native face guidance and Flutter company selection','Login & registration')
    an=native_internal('A',['RegistrationMainActivity','RegistrationUaePassDocumentSignInActivity','RegistrationOpenUaePassActivity','RegistrationUaePassErrorActivity','RegistrationUaePassSubmitErrorActivity','RegistrationTradeLicenseActivity','RegistrationFaceRecognitionGuideActivity','RegistrationFaceRecognitionMainActivity','RegistrationEFRProcessActivity','RegistrationEfrSuccessActivity','RegistrationEfrErrorActivity','RegistrationNewCustomerOnBoardingActivity','RegistrationUaePassEidDetailsActivity','RegistrationSuccessWithUaePassActivity'])
    b.entry(an['RegistrationMainActivity']); b.entry(an['RegistrationUaePassDocumentSignInActivity'])
    eid=f('EidCompaniesScreen')
    b.edge(an['RegistrationOpenUaePassActivity'],eid,'Choose identity companies in Flutter',[evidence('A','navigateToEidCompaniesFlow(this)','registration/uae_pass/RegistrationOpenUaePassActivity'),evidence('F','EidCompaniesCoordinator(', 'core/routes/native_navigation')],kind='return',condition='UAE PASS identity info resolves companies branch')
    for target,cond in [('RegistrationSuccessWithUaePassActivity','isAuthorized == true || isEfrFlow'),('RegistrationUaePassSubmitErrorActivity','CODE_REGISTRATION_UAE_PASS_FETCH_DOCS_ERROR')]:
        b.edge(an['RegistrationTradeLicenseActivity'],an[target],'Registration submit result',[evidence('A','handleRegistrationSubmitResponse(',declaration('A','RegistrationTradeLicenseActivity')),evidence('A',target+'::class.java','core/utils/ExtensionsView')],condition=cond)
    sdk=b.service('efr-native','EFR face/liveness engine',[evidence('A','RegistrationEFRProcessActivity','RegistrationFaceRecognitionMainActivity')])
    b.edge(an['RegistrationFaceRecognitionMainActivity'],sdk,'Execute face verification',[evidence('A','RegistrationEFRProcessActivity','RegistrationFaceRecognitionMainActivity')],kind='service')

    b.journey('ios-registration','iOS BAU registration, identity documents and status','Login & registration')
    ins=native_internal('I',['RegistrationInfoVC','RegistrationOptionsVC','UploadEmirateIDViewController','EmiratesIDDetailVC','TradeLicenseVC','EstablishmentDocumentVC','PowerOfAttorneyVC','RegistrationUserDetailVC','SelfRegistrationMobileNumberVC','OTPMobileVerificationVC','OTPEmailVerificationVC','UAEPassAuthenticationVC','EFRInfoVC','EFRConfigurationVC','CheckRegistrationStatusVC','RegistrationStatusDetailsVC'])
    b.entry(ins['RegistrationInfoVC'])
    # Info uses RegistrationOptionsWrapper whose source defines actual options screen.
    link(ins['RegistrationInfoVC'],ins['RegistrationOptionsVC'],'ReRegistrationOptionsWrapper(', 'Registration/Shared/RegistrationInfo','Continue registration',repo='I')
    b.note('Swift coordinators instantiate the owning storyboard controllers. Guard failures leave the current screen unchanged. UAE PASS / EFR capture and remote/native vendor content require device verification.')

    b.journey('individual-home','Individual and prepaid usage details','Home & accounts')
    individual=f('IndividualDashboardScreen'); prepaid=f('PrepaidHomeScreen'); b.entry(individual); b.entry(prepaid)
    gate=b.decision('usage-product','Account usage type?', 'Android selectedLinkedAccount.accountType MOBILE / BQS / BAIB',[evidence('A','when (selectedAccount.accountType)','FlutterNavigationHandler')])
    for start,hint in [(individual,'dashboard/individual'),(prepaid,'dashboard/prepaid_home')]:
        link(start,gate,'onViewUsageDetail',hint,'View detailed usage • Android','platform == Android')
    for sym,cond in [('UsageMobileFragment','MOBILE'),('UsageBQSFragment','BQS'),('UsageBIBFragment','BAIB')]:
        b.edge(gate,a(sym,kind='content'),'Usage: '+cond,[evidence('A',sym+'::class.java.name','FlutterNavigationHandler')],condition='accountType == '+cond)
    vendor=b.unresolved('ios-usage','iOS daily-usage vendor destination',[evidence('I','openViewDailyUsage','FlutterLinkable')],notes='Native vendor selects the daily usage destination; exact controller is not asserted by this channel handler.')
    for start,hint in [(individual,'dashboard/individual'),(prepaid,'dashboard/prepaid_home')]: link(start,vendor,'onViewUsageDetail',hint,'View detailed usage • iOS','platform == iOS')
    for repo,sym in [('A','PaymentMainActivity'),('I','MakePaymentViewController')]: link(individual,node(repo,sym),'openPayFlow','dashboard/individual','Pay outstanding balance • '+repo,'amount due and product eligibility permit payment; platform == '+repo)
