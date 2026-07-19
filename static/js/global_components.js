document.addEventListener('DOMContentLoaded', () => {
    // ----------------------------------------------------
    // 1. Inject Global Modals and CSS Styles
    // ----------------------------------------------------
    const styles = `
        .global-dropdown {
            display: none;
            position: absolute;
            top: 50px;
            right: 0;
            background: #ffffff;
            border: 1px solid #dde1e6;
            border-radius: 12px;
            box-shadow: 0px 8px 24px rgba(0, 0, 0, 0.08);
            width: 320px;
            z-index: 1000;
            overflow: hidden;
            animation: dropdownFadeIn 0.2s ease-out;
        }
        @keyframes dropdownFadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .app-launcher-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            padding: 16px;
        }
        .app-launcher-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 10px;
            border-radius: 8px;
            transition: all 0.2s;
            text-align: center;
            color: #191c1f;
        }
        .app-launcher-item:hover {
            background-color: #f2f4f8;
            color: #004ccd;
        }
        .app-launcher-item span {
            font-size: 24px;
            margin-bottom: 4px;
        }
        .app-launcher-item p {
            font-size: 11px;
            font-weight: 500;
        }
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(25, 28, 31, 0.4);
            backdrop-filter: blur(4px);
            z-index: 2000;
            align-items: center;
            justify-content: center;
            animation: fadeIn 0.2s ease-out;
        }
        .workflow-modal {
            background: #ffffff;
            border-radius: 16px;
            border: 1px solid #dde1e6;
            width: 90%;
            max-width: 600px;
            box-shadow: 0px 12px 36px rgba(0, 0, 0, 0.12);
            padding: 24px;
            animation: scaleIn 0.2s ease-out;
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        @keyframes scaleIn {
            from { transform: scale(0.95); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
        }
    `;

    const styleSheet = document.createElement("style");
    styleSheet.innerText = styles;
    document.head.appendChild(styleSheet);

    // Inject New Workflow Modal HTML
    const modalHTML = `
        <div class="modal-overlay" id="new-workflow-modal-overlay">
            <div class="workflow-modal">
                <div class="flex justify-between items-start mb-lg border-b border-outline-variant pb-4">
                    <div>
                        <h3 class="font-headline-sm text-headline-sm font-bold text-slate-900">Launch New Workflow</h3>
                        <p class="text-xs text-on-surface-variant mt-0.5">Select a business optimization pipeline to initialize.</p>
                    </div>
                    <button class="text-outline hover:text-on-surface transition-colors" id="close-workflow-modal">
                        <span class="material-symbols-outlined">close</span>
                    </button>
                </div>
                <div class="grid grid-cols-2 gap-md">
                    <!-- Invoice Workflow -->
                    <div class="p-md border border-outline-variant rounded-xl hover:border-primary hover:bg-surface-container-low transition-all cursor-pointer flex flex-col justify-between h-40 group" onclick="window.location.href='/invoices'">
                        <div>
                            <div class="w-8 h-8 rounded-lg bg-blue-50 text-primary flex items-center justify-center mb-sm group-hover:bg-primary group-hover:text-white transition-colors">
                                <span class="material-symbols-outlined text-[20px]">description</span>
                            </div>
                            <h4 class="font-bold text-sm text-slate-800">Process Invoice</h4>
                            <p class="text-[11px] text-on-surface-variant mt-1 leading-relaxed">Upload vendor invoices and execute AI OCR extraction pipeline.</p>
                        </div>
                        <span class="text-xs font-bold text-primary group-hover:translate-x-1 transition-transform flex items-center gap-0.5 mt-2">Initialize &rarr;</span>
                    </div>

                    <!-- Expense Workflow -->
                    <div class="p-md border border-outline-variant rounded-xl hover:border-primary hover:bg-surface-container-low transition-all cursor-pointer flex flex-col justify-between h-40 group" onclick="window.location.href='/expenses'">
                        <div>
                            <div class="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center mb-sm group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                                <span class="material-symbols-outlined text-[20px]">receipt_long</span>
                            </div>
                            <h4 class="font-bold text-sm text-slate-800">Expense Claim</h4>
                            <p class="text-[11px] text-on-surface-variant mt-1 leading-relaxed">File new reimbursement receipt and link to corporate budget.</p>
                        </div>
                        <span class="text-xs font-bold text-indigo-600 group-hover:translate-x-1 transition-transform flex items-center gap-0.5 mt-2">Initialize &rarr;</span>
                    </div>

                    <!-- Leave Workflow -->
                    <div class="p-md border border-outline-variant rounded-xl hover:border-primary hover:bg-surface-container-low transition-all cursor-pointer flex flex-col justify-between h-40 group" onclick="window.location.href='/leave'">
                        <div>
                            <div class="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center mb-sm group-hover:bg-purple-600 group-hover:text-white transition-colors">
                                <span class="material-symbols-outlined text-[20px]">event_busy</span>
                            </div>
                            <h4 class="font-bold text-sm text-slate-800">Request Leave</h4>
                            <p class="text-[11px] text-on-surface-variant mt-1 leading-relaxed">Submit annual, sick, or personal time off for system approval.</p>
                        </div>
                        <span class="text-xs font-bold text-purple-600 group-hover:translate-x-1 transition-transform flex items-center gap-0.5 mt-2">Initialize &rarr;</span>
                    </div>

                    <!-- Payroll Workflow -->
                    <div class="p-md border border-outline-variant rounded-xl hover:border-primary hover:bg-surface-container-low transition-all cursor-pointer flex flex-col justify-between h-40 group" onclick="window.location.href='/payroll'">
                        <div>
                            <div class="w-8 h-8 rounded-lg bg-teal-50 text-teal-600 flex items-center justify-center mb-sm group-hover:bg-teal-600 group-hover:text-white transition-colors">
                                <span class="material-symbols-outlined text-[20px]">payments</span>
                            </div>
                            <h4 class="font-bold text-sm text-slate-800">Disburse Payroll</h4>
                            <p class="text-[11px] text-on-surface-variant mt-1 leading-relaxed">Trigger monthly salary disbursement, calculating deductions.</p>
                        </div>
                        <span class="text-xs font-bold text-teal-600 group-hover:translate-x-1 transition-transform flex items-center gap-0.5 mt-2">Initialize &rarr;</span>
                    </div>
                </div>
            </div>
        </div>
    `;
    const div = document.createElement('div');
    div.innerHTML = modalHTML;
    document.body.appendChild(div);

    // ----------------------------------------------------
    // 2. Apps Launcher & Notifications Setup
    // ----------------------------------------------------
    // Locate notification and apps buttons in the header
    const buttons = document.querySelectorAll('header button');
    let notificationBtn = null;
    let appsBtn = null;

    buttons.forEach(btn => {
        const span = btn.querySelector('.material-symbols-outlined');
        if (span) {
            const iconText = span.textContent.trim();
            if (iconText === 'notifications') {
                notificationBtn = btn;
            } else if (iconText === 'apps') {
                appsBtn = btn;
            }
        }
    });

    // Check if sidebar has Admin Panel link
    const hasAdminLink = !!document.querySelector('aside nav a[href="/admin"]');

    // Create and Inject Apps Dropdown
    if (appsBtn) {
        // Ensure relative wrapper for positioning
        appsBtn.style.position = 'relative';
        
        const appsDropdown = document.createElement('div');
        appsDropdown.className = 'global-dropdown';
        appsDropdown.id = 'global-apps-dropdown';
        
        let appsGridHTML = `
            <div class="app-launcher-grid">
                <a class="app-launcher-item" href="/attendance">
                    <span class="material-symbols-outlined text-primary">calendar_today</span>
                    <p>Attendance</p>
                </a>
                <a class="app-launcher-item" href="/leave">
                    <span class="material-symbols-outlined text-purple-600">event_busy</span>
                    <p>Leave</p>
                </a>
                <a class="app-launcher-item" href="/invoices">
                    <span class="material-symbols-outlined text-blue-500">description</span>
                    <p>Invoices</p>
                </a>
                <a class="app-launcher-item" href="/payroll">
                    <span class="material-symbols-outlined text-teal-600">payments</span>
                    <p>Payroll</p>
                </a>
                <a class="app-launcher-item" href="/expenses">
                    <span class="material-symbols-outlined text-orange-600">receipt_long</span>
                    <p>Expenses</p>
                </a>
                <a class="app-launcher-item" href="/support">
                    <span class="material-symbols-outlined text-slate-600">help</span>
                    <p>Support</p>
                </a>
                <a class="app-launcher-item" href="/settings">
                    <span class="material-symbols-outlined text-slate-500">settings</span>
                    <p>Settings</p>
                </a>
        `;
        
        if (hasAdminLink) {
            appsGridHTML += `
                <a class="app-launcher-item" href="/admin">
                    <span class="material-symbols-outlined text-red-600">shield</span>
                    <p>Admin</p>
                </a>
            `;
        }

        appsGridHTML += `</div>`;
        appsDropdown.innerHTML = appsGridHTML;
        appsBtn.appendChild(appsDropdown);

        appsBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = appsDropdown.style.display === 'block';
            closeAllDropdowns();
            if (!isOpen) {
                appsDropdown.style.display = 'block';
            }
        });
    }

    // Create and Inject Notifications Dropdown
    if (notificationBtn) {
        notificationBtn.style.position = 'relative';

        const notificationsDropdown = document.createElement('div');
        notificationsDropdown.className = 'global-dropdown';
        notificationsDropdown.id = 'global-notifications-dropdown';

        notificationsDropdown.innerHTML = `
            <div class="p-sm bg-surface-container-low border-b border-outline-variant flex justify-between items-center px-md py-2">
                <span class="font-bold text-xs text-slate-800">Notifications</span>
                <button class="text-[10px] text-primary hover:underline font-bold" onclick="event.stopPropagation(); alert('All notifications marked as read.')">Mark read</button>
            </div>
            <div class="max-h-64 overflow-y-auto divide-y divide-outline-variant/30">
                <div class="p-md text-left flex gap-sm hover:bg-slate-50 transition-colors cursor-pointer py-3 px-md">
                    <span class="material-symbols-outlined text-primary text-[18px]">check_circle</span>
                    <div>
                        <p class="text-xs font-bold text-slate-800">Invoice Approved</p>
                        <p class="text-[10px] text-on-surface-variant mt-0.5">INV-2024-001 ($1,240.00) approved.</p>
                        <span class="text-[9px] text-outline mt-1 block">12 mins ago</span>
                    </div>
                </div>
                <div class="p-md text-left flex gap-sm hover:bg-slate-50 transition-colors cursor-pointer py-3 px-md">
                    <span class="material-symbols-outlined text-purple-600 text-[18px]">event_busy</span>
                    <div>
                        <p class="text-xs font-bold text-slate-800">New Leave Request</p>
                        <p class="text-[10px] text-on-surface-variant mt-0.5">Sarah Jenkins requested Annual Leave.</p>
                        <span class="text-[9px] text-outline mt-1 block">1 hour ago</span>
                    </div>
                </div>
                <div class="p-md text-left flex gap-sm hover:bg-slate-50 transition-colors cursor-pointer py-3 px-md">
                    <span class="material-symbols-outlined text-error text-[18px]">warning</span>
                    <div>
                        <p class="text-xs font-bold text-slate-800">Expense Flagged</p>
                        <p class="text-[10px] text-on-surface-variant mt-0.5">NYC Hotel Stay claim requires invoice receipt.</p>
                        <span class="text-[9px] text-outline mt-1 block">3 hours ago</span>
                    </div>
                </div>
                <div class="p-md text-left flex gap-sm hover:bg-slate-50 transition-colors cursor-pointer py-3 px-md">
                    <span class="material-symbols-outlined text-teal-600 text-[18px]">payments</span>
                    <div>
                        <p class="text-xs font-bold text-slate-800">Payroll Cycle Pre-check</p>
                        <p class="text-[10px] text-on-surface-variant mt-0.5">Oct salary disbursal calculation finished.</p>
                        <span class="text-[9px] text-outline mt-1 block">1 day ago</span>
                    </div>
                </div>
            </div>
        `;
        notificationBtn.appendChild(notificationsDropdown);

        notificationBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = notificationsDropdown.style.display === 'block';
            closeAllDropdowns();
            if (!isOpen) {
                notificationsDropdown.style.display = 'block';
            }
        });
    }

    function closeAllDropdowns() {
        const appD = document.getElementById('global-apps-dropdown');
        const notiD = document.getElementById('global-notifications-dropdown');
        if (appD) appD.style.display = 'none';
        if (notiD) notiD.style.display = 'none';
    }

    // Close dropdowns on clicking outside
    document.addEventListener('click', closeAllDropdowns);

    // ----------------------------------------------------
    // 3. New Workflow Modal Trigger
    // ----------------------------------------------------
    // Hook up all sidebar "New Workflow" buttons
    const newWorkflowButtons = document.querySelectorAll('aside button, aside nav + button');
    const overlay = document.getElementById('new-workflow-modal-overlay');
    const closeBtn = document.getElementById('close-workflow-modal');

    // Make sure we catch any button containing "New Workflow"
    document.querySelectorAll('button').forEach(btn => {
        if (btn.textContent.includes('New Workflow')) {
            btn.addEventListener('click', () => {
                overlay.style.display = 'flex';
            });
        }
    });

    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            overlay.style.display = 'none';
        });
    }

    if (overlay) {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.style.display = 'none';
            }
        });
    }

    // ----------------------------------------------------
    // 4. Header Profile Settings Link
    // ----------------------------------------------------
    // Find top header profile area
    const profileContainers = document.querySelectorAll('header .flex.items-center.gap-sm, #header-profile-trigger');
    profileContainers.forEach(container => {
        // Only wrap if it contains an image (profile photo)
        if (!container.querySelector('img')) return;
        
        const parent = container.parentElement;
        if (parent && parent.tagName !== 'A') {
            const anchor = document.createElement('a');
            anchor.href = '/settings';
            anchor.className = 'flex items-center gap-sm hover:opacity-80 transition-opacity';
            
            // Move children into anchor
            while (container.firstChild) {
                anchor.appendChild(container.firstChild);
            }
            container.appendChild(anchor);
        }
    });

    // ----------------------------------------------------
    // 5. Client-Side Search Functionality
    // ----------------------------------------------------
    // Select any input in the header that looks like a search bar
    const searchInput = document.querySelector('header input[type="text"]');
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            const query = searchInput.value.toLowerCase().trim();
            
            // Check if page has pagination variables or tables
            // If the page has global functions searchTable or showPage, we will trigger it if present.
            // Otherwise, we do standard row-based string matching.
            if (typeof window.triggerClientSearch === 'function') {
                window.triggerClientSearch(query);
            } else {
                // Fallback direct table search
                const rows = document.querySelectorAll('tbody tr');
                rows.forEach(row => {
                    const text = row.textContent.toLowerCase();
                    if (text.includes(query)) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                });
            }
        });
    }
});
