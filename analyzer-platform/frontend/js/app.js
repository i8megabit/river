/**
 * Веб-платформа анализатора сетевых соединений
 * Написано на ванильном JavaScript с ES6+ синтаксисом
 */

class AnalyzerApp {
    constructor() {
        console.log('🚀 Инициализация Analyzer Platform...');
        
        // Базовый URL для API (бэкенд на порту 18000 в тестовой конфигурации)
        this.API_BASE_URL = 'http://localhost:18000';
        
        this.currentReport = null;
        this.currentTab = 'overview';
        this.reports = [];
        this.appInfo = null;
        
        this.init();
    }
    
    async init() {
        await this.loadAppInfo();
        this.bindEvents();
        this.loadReports();
    }
    
    // Загрузка информации о приложении
    async loadAppInfo() {
        try {
            const response = await fetch(`${this.API_BASE_URL}/api/v1/app/info`);
            if (response.ok) {
                this.appInfo = await response.json();
                this.updateAppTitle();
            }
        } catch (error) {
            console.error('❌ Ошибка загрузки информации о приложении:', error);
        }
    }
    
    // Обновление заголовка приложения с версией
    updateAppTitle() {
        if (this.appInfo) {
            const titleElement = document.querySelector('.app-title h1');
            if (titleElement) {
                titleElement.textContent = `${this.appInfo.name} ${this.appInfo.version}`;
            }
        }
    }
    
    bindEvents() {
        // Проверяем, что все элементы загружены
        const requiredElements = [
            'reports-tab', 'refresh-btn', 'upload-btn', 'search-input',
            'total-reports', 'total-connections', 'total-hosts',
            'loading-state', 'empty-state', 'reports-grid'
        ];
        
        for (const elementId of requiredElements) {
            const element = document.getElementById(elementId);
            if (!element) {
                console.error(`❌ Элемент не найден: ${elementId}`);
                return;
            }
        }
        
        console.log('✅ Все DOM элементы найдены');
        
        // Навигация
        document.getElementById('reports-tab').addEventListener('click', () => this.showReportsScreen());
        document.getElementById('refresh-btn').addEventListener('click', () => this.loadReports());
        document.getElementById('upload-btn').addEventListener('click', () => this.showUploadDialog());
        
        // Поиск
        const searchInput = document.getElementById('search-input');
        searchInput.addEventListener('input', (e) => this.performSearch(e.target.value));
        
        // Табы детального просмотра
        document.querySelectorAll('.tab-button').forEach(button => {
            button.addEventListener('click', (e) => this.switchTab(e.target.dataset.tab));
        });
        
        // Модальное окно
        document.getElementById('modal-close').addEventListener('click', () => this.hideUploadDialog());
        document.getElementById('cancel-upload').addEventListener('click', () => this.hideUploadDialog());
        document.getElementById('confirm-upload').addEventListener('click', () => this.uploadFile());
        
        // Загрузка файлов
        const uploadArea = document.getElementById('upload-area');
        const fileInput = document.getElementById('file-input');
        
        uploadArea.addEventListener('click', () => fileInput.click());
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            this.handleFileSelect(e.dataTransfer.files[0]);
        });
        
        fileInput.addEventListener('change', (e) => this.handleFileSelect(e.target.files[0]));
        
        // Закрытие модального окна при клике вне его
        document.getElementById('upload-modal').addEventListener('click', (e) => {
            if (e.target.id === 'upload-modal') {
                this.hideUploadDialog();
            }
        });
    }
    
    // Загрузка списка отчетов
    async loadReports() {
        console.log('🔄 Начинаем загрузку отчетов...');
        this.showLoading();
        
        try {
            console.log('📡 Отправляем запрос к API...');
            const response = await fetch(`${this.API_BASE_URL}/api/v1/reports`);
            console.log('📡 Получен ответ от API:', response.status, response.statusText);
            
            if (!response.ok) throw new Error('Failed to fetch reports');
            
            const data = await response.json();
            console.log('📄 Данные от API:', data);
            
            this.reports = data.reports || [];
            console.log('📊 Загружено отчетов:', this.reports.length);
            
            // Отладочный вывод данных из API
            console.log('📡 Данные от API:', {
                total: data.total,
                reports_count: this.reports.length,
                first_report_sample: this.reports[0] ? {
                    hostname: this.reports[0].hostname,
                    tcp_ports_count: this.reports[0].tcp_ports_count,
                    udp_ports_count: this.reports[0].udp_ports_count,
                    total_connections: this.reports[0].total_connections
                } : null
            });
            
            this.renderReports();
            this.updateHeaderStats();
        } catch (error) {
            console.error('❌ Ошибка загрузки отчетов:', error);
            this.showNotification('Ошибка загрузки отчетов', 'error');
            this.showEmptyState();
        }
    }
    
    // Отображение списка отчетов
    renderReports() {
        const container = document.getElementById('reports-grid');
        const loadingState = document.getElementById('loading-state');
        const emptyState = document.getElementById('empty-state');
        
        loadingState.style.display = 'none';
        
        if (this.reports.length === 0) {
            emptyState.style.display = 'block';
            container.style.display = 'none';
            return;
        }
        
        emptyState.style.display = 'none';
        container.style.display = 'grid';
        
        // Отладочный вывод для проверки данных о портах
        console.log('🔍 Отладка портов в отчетах:');
        this.reports.forEach((report, index) => {
            const tcpPorts = report.tcp_ports_count || 0;
            const udpPorts = report.udp_ports_count || 0;
            const totalPorts = tcpPorts + udpPorts;
            console.log(`Report ${index + 1} (${report.hostname}): TCP=${tcpPorts}, UDP=${udpPorts}, Total=${totalPorts}`);
        });
        
        container.innerHTML = this.reports.map(report => `
            <div class="report-card" data-report-id="${report.id}" style="cursor: pointer;">
                <div class="report-card-header">
                    <div class="report-title">${report.hostname || 'Неизвестный хост'}</div>
                    <div class="report-meta">
                        <span>📅 ${this.formatDate(report.generated_at)}</span>
                        <span>💻 ${report.os_name || this.formatOS(report.os) || 'Неизвестная ОС'}</span>
                    </div>
                </div>
                <div class="report-body">
                    <div class="report-stats">
                        <div class="stat-item">
                            <span class="stat-number">${report.total_connections || 0}</span>
                            <span class="stat-text">Соединения</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-number">${(report.tcp_ports_count || 0) + (report.udp_ports_count || 0)}</span>
                            <span class="stat-text">Порты</span>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
        
        // Добавляем обработчики событий для карточек отчетов
        container.querySelectorAll('.report-card').forEach(card => {
            card.addEventListener('click', (e) => {
                const reportId = e.currentTarget.dataset.reportId;
                this.showReportDetail(reportId);
            });
        });
    }
    
    // Показать детальный просмотр отчета
    async showReportDetail(reportId) {
        try {
            console.log(`🔍 Загружаем детали отчета: ${reportId}`);
            
            // Получаем отчет из списка для получения метаданных
            const report = this.reports.find(r => r.id === reportId);
            
            console.log(`🔍 Загружаем полные данные отчета: ${reportId}`);
            
            // Используем полный endpoint с данными о соединениях и портах
            const response = await fetch(`${this.API_BASE_URL}/api/v1/reports/${reportId}`);
            if (!response.ok) {
                console.error(`❌ Ошибка ${response.status}: ${response.statusText}`);
                throw new Error('Failed to fetch report details');
            }
            
            const fullData = await response.json();
            console.log(`✅ Получены полные данные отчета:`, fullData);
            
            // Используем полные данные
            this.currentReport = {
                id: reportId,
                hostname: fullData.hostname || report?.hostname || 'Неизвестный хост',
                os: fullData.os || { name: report?.os_name || 'Неизвестная ОС', version: '' },
                file_size: fullData.file_size || report?.file_size || 0,
                status: fullData.status || 'unknown',
                created_at: fullData.created_at || report?.generated_at || new Date().toISOString(),
                total_connections: fullData.total_connections || report?.total_connections || 0,
                tcp_connections: fullData.tcp_connections || 0,
                udp_connections: fullData.udp_connections || 0,
                listening_ports: fullData.listening_ports || 0,
                established_connections: fullData.established_connections || 0,
                total_ports: fullData.total_ports || ((report?.tcp_ports_count || 0) + (report?.udp_ports_count || 0)),
                // Используем реальные данные о соединениях и портах
                connections: Array.isArray(fullData.connections) ? fullData.connections : [],
                ports: Array.isArray(fullData.ports) ? fullData.ports : [],
                icmp_connections: fullData.icmp_connections || 0
            };
            
            console.log(`✅ Адаптированные данные отчета:`, {
                id: this.currentReport.id,
                hostname: this.currentReport.hostname,
                connections_count: this.currentReport.connections.length,
                ports_count: this.currentReport.ports.length,
                connections_sample: this.currentReport.connections[0],
                ports_sample: this.currentReport.ports[0]
            });
            
            this.renderReportDetail();
            this.showDetailScreen();
        } catch (error) {
            console.error('Error loading report details:', error);
            this.showNotification(`Ошибка загрузки деталей отчета: ${error.message}`, 'error');
        }
    }
    
    // Отображение детального просмотра
    renderReportDetail() {
        const title = document.getElementById('detail-title');
        const meta = document.getElementById('detail-meta');
        
        title.textContent = `Анализ: ${this.currentReport.hostname || 'Неизвестный хост'}`;
        
        meta.innerHTML = `
            <div class="meta-item">
                <span class="meta-label">Hostname</span>
                <span class="meta-value">${this.currentReport.hostname || 'N/A'}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Операционная система</span>
                <span class="meta-value">${this.formatOS(this.currentReport.os)}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Дата создания</span>
                <span class="meta-value">${this.formatDate(this.currentReport.created_at)}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Размер файла</span>
                <span class="meta-value">${this.formatFileSize(this.currentReport.file_size)}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Всего соединений</span>
                <span class="meta-value">${this.currentReport.total_connections || 0}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Всего портов</span>
                <span class="meta-value">${this.currentReport.total_ports || 0}</span>
            </div>
        `;
        
        this.renderTabContent('overview');
    }
    
    // Отображение содержимого табов
    renderTabContent(tab) {
        const content = document.getElementById('tab-content');
        
        switch (tab) {
            case 'overview':
                content.innerHTML = this.renderOverviewTab();
                break;
            case 'connections':
                content.innerHTML = this.renderConnectionsTab();
                break;
            case 'ports':
                content.innerHTML = this.renderPortsTab();
                break;
            case 'hosts':
                content.innerHTML = this.renderHostsTab();
                break;
        }
        
        // Добавляем обработчики событий после рендеринга
        this.addTabEventListeners(tab);
    }
    
    // Добавление обработчиков событий для содержимого табов
    addTabEventListeners(tab) {
        if (tab === 'overview' && this.currentReport) {
            const downloadBtn = document.getElementById(`download-btn-${this.currentReport.id}`);
            if (downloadBtn) {
                downloadBtn.addEventListener('click', () => {
                    this.downloadReport(this.currentReport.id);
                });
            }
        }
    }
    
    // Таб "Обзор"
    renderOverviewTab() {
        const data = this.currentReport;
        return `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 2rem;">
                <div style="background: var(--background); padding: 1.5rem; border-radius: var(--radius);">
                    <h4 style="margin-bottom: 1rem; color: var(--text-primary);">📊 Статистика соединений</h4>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;">
                        <div style="text-align: center;">
                            <div style="font-size: 2rem; font-weight: 700; color: var(--primary);">${data.tcp_connections || 0}</div>
                            <div style="font-size: 0.875rem; color: var(--text-secondary);">TCP</div>
                        </div>
                        <div style="text-align: center;">
                            <div style="font-size: 2rem; font-weight: 700; color: var(--success);">${data.udp_connections || 0}</div>
                            <div style="font-size: 0.875rem; color: var(--text-secondary);">UDP</div>
                        </div>
                        <div style="text-align: center;">
                            <div style="font-size: 2rem; font-weight: 700; color: var(--warning);">${data.icmp_connections || 0}</div>
                            <div style="font-size: 0.875rem; color: var(--text-secondary);">ICMP</div>
                        </div>
                    </div>
                </div>
                
                <div style="background: var(--background); padding: 1.5rem; border-radius: var(--radius);">
                    <h4 style="margin-bottom: 1rem; color: var(--text-primary);">🌐 Сетевая активность</h4>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem;">
                        <div style="text-align: center;">
                            <div style="font-size: 2rem; font-weight: 700; color: var(--warning);">${data.listening_ports || 0}</div>
                            <div style="font-size: 0.875rem; color: var(--text-secondary);">Listening</div>
                        </div>
                        <div style="text-align: center;">
                            <div style="font-size: 2rem; font-weight: 700; color: var(--danger);">${data.established_connections || 0}</div>
                            <div style="font-size: 0.875rem; color: var(--text-secondary);">Established</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div style="margin-top: 2rem;">
                <h4 style="margin-bottom: 1rem; color: var(--text-primary);">🔍 Основная информация</h4>
                <div style="background: var(--background); padding: 1.5rem; border-radius: var(--radius);">
                    <p style="margin-bottom: 0.5rem;"><strong>Имя хоста:</strong> ${data.hostname || 'N/A'}</p>
                    <p style="margin-bottom: 0.5rem;"><strong>ОС:</strong> ${this.formatOS(data.os)}</p>
                    <p style="margin-bottom: 0.5rem;"><strong>Дата анализа:</strong> ${this.formatDate(data.created_at)}</p>
                    <p style="margin-bottom: 0.5rem;"><strong>Размер отчета:</strong> ${this.formatFileSize(data.file_size)}</p>
                </div>
            </div>
            
            <div style="margin-top: 2rem;">
                <button class="btn btn-primary" data-download-report="${data.id}" id="download-btn-${data.id}">
                    <i data-lucide="download" style="width: 1rem; height: 1rem;"></i>
                    Скачать оригинальный HTML
                </button>
            </div>
        `;
    }
    
    // Таб "Соединения"
    renderConnectionsTab() {
        const connections = Array.isArray(this.currentReport.connections) ? this.currentReport.connections : [];
        
        return `
            <h4 style="margin-bottom: 1.5rem; color: var(--text-primary);">🔗 Активные соединения (${connections.length})</h4>
            <div style="overflow-x: auto;">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Тип</th>
                            <th>Протокол</th>
                            <th>Локальный адрес</th>
                            <th>Удаленный адрес</th>
                            <th>Процесс</th>
                            <th>Пакеты</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${connections.map(conn => `
                            <tr>
                                <td>
                                    <span style="padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; 
                                                 background: ${conn.type === 'incoming' ? 'var(--success-bg)' : 'var(--primary-bg)'}; 
                                                 color: ${conn.type === 'incoming' ? 'var(--success)' : 'var(--primary)'};">
                                        ${conn.type === 'incoming' ? '📥 Входящее' : '📤 Исходящее'}
                                    </span>
                                </td>
                                <td style="font-weight: 600; color: ${this.getProtocolColor(conn.protocol)}">${conn.protocol || 'unknown'}</td>
                                <td><code>${conn.local_address || 'N/A'}</code></td>
                                <td><code>${conn.remote_address || 'N/A'}</code></td>
                                <td style="font-family: monospace; font-size: 0.9em;">${conn.process || 'unknown'}</td>
                                <td style="text-align: center;">${conn.packet_count || 0}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
                ${connections.length === 0 ? '<p style="text-align: center; color: var(--text-secondary); margin-top: 2rem;">Нет данных о соединениях</p>' : ''}
            </div>
        `;
    }
    
    // Таб "Порты"
    renderPortsTab() {
        const ports = Array.isArray(this.currentReport.ports) ? this.currentReport.ports : [];
        
        return `
            <h4 style="margin-bottom: 1.5rem; color: var(--text-primary);">🚪 Открытые порты (${ports.length})</h4>
            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; margin-bottom: 2rem;">
                ${ports.map(port => `
                    <div style="background: var(--background); padding: 1.5rem; border-radius: var(--radius); border-left: 4px solid ${this.getProtocolColor(port.protocol)};">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                            <span style="font-size: 1.25rem; font-weight: 700; color: var(--primary);">${port.port_number || 'N/A'}</span>
                            <span style="font-weight: 600; color: ${this.getProtocolColor(port.protocol)}">${(port.protocol || 'unknown').toUpperCase()}</span>
                        </div>
                        <div style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 0.5rem;">
                            ${port.description || port.service_name || 'Неизвестная служба'}
                        </div>
                        <div style="font-size: 0.75rem; color: var(--text-secondary);">
                            Состояние: ${port.status || 'N/A'}
                        </div>
                        ${port.process ? `<div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem;">
                            Процесс: ${port.process}
                        </div>` : ''}
                    </div>
                `).join('')}
            </div>
            ${ports.length === 0 ? '<p style="text-align: center; color: var(--text-secondary); margin-top: 2rem;">Нет данных о портах</p>' : ''}
        `;
    }
    
    // Таб "Хосты"
    renderHostsTab() {
        const connections = Array.isArray(this.currentReport.connections) ? this.currentReport.connections : [];
        
        // Собираем уникальные хосты из соединений
        const hostsMap = new Map();
        
        connections.forEach(conn => {
            // Извлекаем хост из удаленного адреса
            if (conn.remote_address && conn.remote_address !== 'N/A' && conn.remote_address !== '-') {
                const address = conn.remote_address.includes(':') 
                    ? conn.remote_address.split(':')[0] 
                    : conn.remote_address;
                
                if (address && address !== '*' && address !== '0.0.0.0' && address !== '127.0.0.1') {
                    if (!hostsMap.has(address)) {
                        hostsMap.set(address, {
                            address: address,
                            connections: [],
                            protocols: new Set(),
                            connectionTypes: new Set()
                        });
                    }
                    
                    const host = hostsMap.get(address);
                    host.connections.push(conn);
                    if (conn.protocol) host.protocols.add(conn.protocol.toUpperCase());
                    if (conn.type) host.connectionTypes.add(conn.type);
                }
            }
        });
        
        const uniqueHosts = Array.from(hostsMap.values());
        
        return `
            <h4 style="margin-bottom: 1.5rem; color: var(--text-primary);">🌐 Уникальные хосты (${uniqueHosts.length})</h4>
            
            ${uniqueHosts.length > 0 ? `
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 1rem; margin-bottom: 2rem;">
                    ${uniqueHosts.map(host => {
                        const protocols = Array.from(host.protocols).join(', ');
                        const connectionTypes = Array.from(host.connectionTypes);
                        const hasIncoming = connectionTypes.includes('incoming');
                        const hasOutgoing = connectionTypes.includes('outgoing');
                        
                        return `
                            <div style="background: var(--background); padding: 1.5rem; border-radius: var(--radius); border-left: 4px solid var(--primary);">
                                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
                                    <div>
                                        <div style="font-size: 1.1rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.25rem;">
                                            ${host.address}
                                        </div>
                                        <div style="font-size: 0.875rem; color: var(--text-secondary);">
                                            ${protocols || 'Неизвестные протоколы'}
                                        </div>
                                    </div>
                                    <div style="font-size: 1.25rem; font-weight: 700; color: var(--primary);">
                                        ${host.connections.length}
                                    </div>
                                </div>
                                
                                <div style="display: flex; gap: 0.5rem; margin-bottom: 1rem;">
                                    ${hasIncoming ? `
                                        <span style="padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; 
                                                     background: var(--success-bg); color: var(--success);">
                                            📥 Входящие
                                        </span>
                                    ` : ''}
                                    ${hasOutgoing ? `
                                        <span style="padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; 
                                                     background: var(--primary-bg); color: var(--primary);">
                                            📤 Исходящие
                                        </span>
                                    ` : ''}
                                </div>
                                
                                <div style="font-size: 0.75rem; color: var(--text-secondary);">
                                    <div>Всего соединений: ${host.connections.length}</div>
                                    <div>Протоколы: ${protocols}</div>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
                
                <div style="margin-top: 2rem;">
                    <h5 style="margin-bottom: 1rem; color: var(--text-primary);">📊 Статистика хостов</h5>
                    <div style="background: var(--background); padding: 1.5rem; border-radius: var(--radius);">
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
                            <div style="text-align: center;">
                                <div style="font-size: 2rem; font-weight: 700; color: var(--primary);">${uniqueHosts.length}</div>
                                <div style="font-size: 0.875rem; color: var(--text-secondary);">Уникальных хостов</div>
                            </div>
                            <div style="text-align: center;">
                                <div style="font-size: 2rem; font-weight: 700; color: var(--success);">${uniqueHosts.filter(h => h.connectionTypes.has('incoming')).length}</div>
                                <div style="font-size: 0.875rem; color: var(--text-secondary);">С входящими</div>
                            </div>
                            <div style="text-align: center;">
                                <div style="font-size: 2rem; font-weight: 700; color: var(--warning);">${uniqueHosts.filter(h => h.connectionTypes.has('outgoing')).length}</div>
                                <div style="font-size: 0.875rem; color: var(--text-secondary);">С исходящими</div>
                            </div>
                        </div>
                    </div>
                </div>
            ` : `
                <p style="text-align: center; color: var(--text-secondary); margin-top: 2rem;">
                    Нет данных об уникальных хостах
                </p>
            `}
        `;
    }
    
    // Переключение табов
    switchTab(tab) {
        // Обновляем активную кнопку
        document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
        document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
        
        this.currentTab = tab;
        this.renderTabContent(tab);
        
        // Переинициализируем иконки после обновления содержимого
        setTimeout(() => lucide.createIcons(), 100);
    }
    
    // Поиск по отчетам
    performSearch(query) {
        if (!query) {
            this.renderReports();
            return;
        }
        
        const filteredReports = this.reports.filter(report => 
            report.hostname?.toLowerCase().includes(query.toLowerCase()) ||
            report.os_name?.toLowerCase().includes(query.toLowerCase())
        );
        
        const container = document.getElementById('reports-grid');
        container.innerHTML = filteredReports.map(report => `
            <div class="report-card" data-report-id="${report.id}" style="cursor: pointer;">
                <div class="report-card-header">
                    <div class="report-title">${report.hostname || 'Неизвестный хост'}</div>
                    <div class="report-meta">
                        <span>📅 ${this.formatDate(report.generated_at)}</span>
                        <span>💻 ${report.os_name || this.formatOS(report.os) || 'Неизвестная ОС'}</span>
                    </div>
                </div>
                <div class="report-body">
                    <div class="report-stats">
                        <div class="stat-item">
                            <span class="stat-number">${report.total_connections || 0}</span>
                            <span class="stat-text">Соединения</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-number">${(report.tcp_ports_count || 0) + (report.udp_ports_count || 0)}</span>
                            <span class="stat-text">Порты</span>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
        
        // Добавляем обработчики событий для отфильтрованных карточек отчетов
        container.querySelectorAll('.report-card').forEach(card => {
            card.addEventListener('click', (e) => {
                const reportId = e.currentTarget.dataset.reportId;
                this.showReportDetail(reportId);
            });
        });
    }
    
    // Показать диалог загрузки
    showUploadDialog() {
        document.getElementById('upload-modal').classList.add('active');
    }
    
    // Скрыть диалог загрузки
    hideUploadDialog() {
        document.getElementById('upload-modal').classList.remove('active');
        document.getElementById('file-input').value = '';
        document.getElementById('report-name').value = '';
        document.getElementById('confirm-upload').disabled = true;
    }
    
    // Обработка выбора файла
    handleFileSelect(file) {
        if (!file) return;
        
        if (file.type !== 'text/html' && !file.name.endsWith('.html')) {
            this.showNotification('Пожалуйста, выберите HTML файл', 'error');
            return;
        }
        
        this.selectedFile = file;
        document.getElementById('confirm-upload').disabled = false;
        
        // Автоматически заполняем название отчета
        const reportName = document.getElementById('report-name');
        if (!reportName.value) {
            reportName.value = file.name.replace('.html', '');
        }
    }
    
    // Загрузка файла
    async uploadFile() {
        if (!this.selectedFile) {
            this.showNotification('Пожалуйста, выберите файл', 'error');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', this.selectedFile);
        
        try {
            this.showNotification('Загрузка файла...', 'info');
            
            const response = await fetch(`${this.API_BASE_URL}/api/v1/reports/upload`, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) throw new Error('Upload failed');
            
            const result = await response.json();
            this.showNotification('Файл успешно загружен!', 'success');
            this.hideUploadDialog();
            this.loadReports(); // Обновляем список отчетов
            
        } catch (error) {
            console.error('Upload error:', error);
            this.showNotification('Ошибка загрузки файла', 'error');
        }
    }
    
    // Скачивание отчета
    async downloadReport(reportId) {
        try {
            const response = await fetch(`${this.API_BASE_URL}/api/v1/reports/${reportId}/download`);
            if (!response.ok) throw new Error('Download failed');
            
            // Получаем имя файла из заголовков ответа
            let filename = 'report.html';
            const contentDisposition = response.headers.get('Content-Disposition');
            
            if (contentDisposition) {
                // Ищем filename= в заголовке
                const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
                if (filenameMatch && filenameMatch[1]) {
                    filename = filenameMatch[1];
                    // Убираем кавычки если они есть
                    filename = filename.replace(/['"]/g, '');
                    // Убираем лишние символы в начале и конце
                    filename = filename.trim();
                }
            }
            
            console.log('📥 Скачиваем файл:', filename);
            
            // Создаем ссылку для скачивания
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            this.showNotification('Отчет успешно скачан', 'success');
        } catch (error) {
            console.error('Download error:', error);
            this.showNotification('Ошибка скачивания отчета', 'error');
        }
    }
    
    // Экраны
    showReportsScreen() {
        document.querySelectorAll('.screen').forEach(screen => screen.classList.remove('active'));
        document.getElementById('reports-screen').classList.add('active');
    }
    
    showDetailScreen() {
        document.querySelectorAll('.screen').forEach(screen => screen.classList.remove('active'));
        document.getElementById('detail-screen').classList.add('active');
    }
    
    showLoading() {
        document.getElementById('loading-state').style.display = 'flex';
        document.getElementById('empty-state').style.display = 'none';
        document.getElementById('reports-grid').style.display = 'none';
    }
    
    showEmptyState() {
        document.getElementById('loading-state').style.display = 'none';
        document.getElementById('empty-state').style.display = 'block';
        document.getElementById('reports-grid').style.display = 'none';
    }
    
    // Обновление статистики в заголовке
    async updateHeaderStats() {
        try {
            // Получаем статистику от API
            const response = await fetch(`${this.API_BASE_URL}/api/v1/reports/stats/summary`);
            if (response.ok) {
                const stats = await response.json();
                console.log('📊 Статистика от API:', stats);
                
                document.getElementById('total-reports').textContent = stats.total_reports || 0;
                document.getElementById('total-connections').textContent = stats.total_connections || 0;
                document.getElementById('total-hosts').textContent = stats.unique_hosts || 0;
            } else {
                // Fallback: считаем из локальных данных
                console.log('⚠️ API статистики недоступен, используем fallback');
                this.updateHeaderStatsFallback();
            }
        } catch (error) {
            console.error('❌ Ошибка получения статистики от API:', error);
            // Fallback: считаем из локальных данных
            this.updateHeaderStatsFallback();
        }
    }
    
    // Fallback функция для подсчета статистики из локальных данных
    updateHeaderStatsFallback() {
        const totalReports = this.reports.length;
        const totalConnections = this.reports.reduce((sum, report) => sum + (report.total_connections || 0), 0);
        const uniqueHostnames = new Set(this.reports.map(report => report.hostname)).size;
        
        document.getElementById('total-reports').textContent = totalReports;
        document.getElementById('total-connections').textContent = totalConnections;
        document.getElementById('total-hosts').textContent = uniqueHostnames;
        
        console.log('📊 Fallback статистика:', {
            totalReports,
            totalConnections,
            uniqueHostnames
        });
    }
    
    // Уведомления
    showNotification(message, type = 'success') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <i data-lucide="${type === 'success' ? 'check-circle' : 'alert-circle'}" style="width: 1rem; height: 1rem;"></i>
                <span>${message}</span>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Инициализируем иконку
        lucide.createIcons();
        
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
    
    // Вспомогательные методы
    formatDate(dateString) {
        if (!dateString) return 'N/A';
        return new Date(dateString).toLocaleString('ru-RU');
    }
    
    formatFileSize(bytes) {
        if (!bytes) return 'N/A';
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
    }
    
    getProtocolColor(protocol) {
        switch (protocol?.toLowerCase()) {
            case 'tcp': return 'var(--primary)';
            case 'udp': return 'var(--success)';
            case 'icmp': return 'var(--danger)';
            default: return 'var(--secondary)';
        }
    }
    
    getStateColor(state) {
        switch (state?.toLowerCase()) {
            case 'established': return 'var(--success)';
            case 'listening': return 'var(--primary)';
            case 'time_wait': return 'var(--warning)';
            case 'close_wait': return 'var(--danger)';
            default: return 'var(--secondary)';
        }
    }
    
    formatOS(os) {
        if (!os) return 'Неизвестная ОС';
        
        // Если os это объект, извлекаем name и version
        if (typeof os === 'object' && os !== null) {
            const name = os.name || 'Unknown';
            const version = os.version || '';
            
            if (name === 'Unknown') {
                return 'Неизвестная ОС';
            }
            
            return version ? `${name} ${version}` : name;
        }
        
        // Если os это строка
        if (typeof os === 'string') {
            if (os === 'Unknown' || os.trim() === '') {
                return 'Неизвестная ОС';
            }
            return os;
        }
        
        // В остальных случаях
        return String(os) || 'Неизвестная ОС';
    }
}

// Создаем глобальную переменную app с заглушками для методов, чтобы избежать ошибок до загрузки
window.app = {
    showReportDetail: function(reportId) {
        console.log('🔄 Приложение еще загружается, ожидание...', reportId);
        // Ждем инициализации и повторно вызываем метод
        const checkAndCall = () => {
            if (window.app && window.app.constructor === AnalyzerApp) {
                window.app.showReportDetail(reportId);
            } else {
                setTimeout(checkAndCall, 50);
            }
        };
        setTimeout(checkAndCall, 10);
    }
};

// Инициализация приложения после загрузки DOM
document.addEventListener('DOMContentLoaded', () => {
    console.log('🔄 DOM загружен, инициализация приложения...');
    window.app = new AnalyzerApp();
}); 