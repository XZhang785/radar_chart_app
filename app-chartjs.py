"""
雷达图分析工具 - Chart.js 版本（完整功能复刻）
复刻 ECharts 版本的所有功能
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pandas as pd
import numpy as np
from io import BytesIO
import os

app = FastAPI(title="雷达图分析工具 - Chart.js版")

# 获取当前文件目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 挂载静态文件
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


def read_file(file_content: bytes, filename: str) -> pd.DataFrame:
    """读取文件"""
    file_extension = filename.lower().split('.')[-1]
    
    try:
        if file_extension == 'csv':
            try:
                df = pd.read_csv(BytesIO(file_content), encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(BytesIO(file_content), encoding='gbk')
        elif file_extension in ['xlsx', 'xls']:
            df = pd.read_excel(BytesIO(file_content))
        else:
            raise ValueError(f"不支持的文件格式: {file_extension}")
        return df
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件读取错误: {str(e)}")


def validate_data(df: pd.DataFrame) -> dict:
    """验证数据格式"""
    if df.shape[1] < 2:
        raise HTTPException(status_code=400, detail="数据至少需要2列")
    if df.shape[0] < 2:
        raise HTTPException(status_code=400, detail="数据至少需要2行")
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(numeric_cols) < 1:
        raise HTTPException(status_code=400, detail="数据中至少需要有1列数值数据")
    
    return {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "numeric_columns": len(numeric_cols)
    }


def calculate_radar_data(df: pd.DataFrame) -> dict:
    """计算雷达图数据"""
    labels = df.iloc[:, 0].astype(str).tolist()
    data_df = df.iloc[:, 1:].select_dtypes(include=[np.number])
    columns = data_df.columns.tolist()
    
    if len(columns) == 0:
        raise HTTPException(status_code=400, detail="未找到数值列")
    
    column_means = data_df.mean().tolist()
    max_values = data_df.max()
    min_values = data_df.min()
    
    ranges = max_values - min_values
    ranges = ranges.replace(0, 1)
    
    normalized_data = (data_df - min_values) / ranges
    normalized_means = [
        (column_means[i] - min_values.iloc[i]) / ranges.iloc[i] 
        if ranges.iloc[i] != 0 else column_means[i] 
        for i in range(len(column_means))
    ]
    
    rows_data = []
    for idx, label in enumerate(labels):
        row_values = normalized_data.iloc[idx].tolist()
        rows_data.append({
            "label": label,
            "original_values": data_df.iloc[idx].tolist(),
            "normalized_values": row_values
        })
    
    return {
        "indicators": [{"Name": str(col), "max": 1.0, "min": 0.0} for col in columns],
        "average": {
            "original": column_means,
            "normalized": normalized_means
        },
        "rows": rows_data,
        "columns": columns,
        "summary": {
            "total_rows": len(labels),
            "total_columns": len(columns),
            "min_values": min_values.tolist(),
            "max_values": max_values.tolist()
        }
    }


@app.get("/", response_class=HTMLResponse)
async def home():
    """返回主页 - Chart.js 版本（完整功能）"""
    html = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>雷达图分析工具 - Chart.js版本</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
            .container { max-width: 1400px; margin: 0 auto; }
            
            /* 头部 */
            .header { text-align: center; color: white; margin-bottom: 30px; }
            .header h1 { font-size: 2.5rem; font-weight: 700; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.2); }
            .header p { font-size: 1.1rem; opacity: 0.9; }
            
            /* 上传区域 */
            .upload-section { background: white; border-radius: 16px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.15); }
            .upload-area { border: 3px dashed #e0e0e0; border-radius: 12px; padding: 50px 30px; text-align: center; transition: all 0.3s ease; cursor: pointer; }
            .upload-area:hover, .upload-area.dragover { border-color: #667eea; background: #f8f6ff; }
            .upload-icon { font-size: 4rem; margin-bottom: 15px; }
            .upload-text { font-size: 1.2rem; color: #666; margin-bottom: 10px; }
            .upload-hint { font-size: 0.9rem; color: #999; }
            #fileInput { display: none; }
            .upload-btn { display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 30px; border-radius: 25px; font-size: 1rem; cursor: pointer; border: none; margin-top: 15px; }
            
            /* 文件信息 */
            .file-info { display: none; margin-top: 20px; padding: 15px 20px; background: #f0f9ff; border-radius: 10px; border-left: 4px solid #667eea; }
            .file-info.show { display: flex; align-items: center; gap: 15px; }
            .file-name { font-weight: 600; color: #333; }
            .file-stats { font-size: 0.9rem; color: #666; margin-top: 5px; }
            .file-remove { background: #ff4757; color: white; border: none; padding: 8px 15px; border-radius: 6px; cursor: pointer; }
            
            /* Tab 导航 */
            .tab-navigation { display: none; background: white; border-radius: 16px 16px 0 0; padding: 0 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.15); }
            .tab-navigation.show { display: flex; }
            .tab-btn { padding: 18px 30px; border: none; background: transparent; font-size: 1rem; font-weight: 600; color: #666; cursor: pointer; border-bottom: 3px solid transparent; transition: all 0.3s ease; }
            .tab-btn:hover { color: #667eea; background: #f8f6ff; }
            .tab-btn.active { color: #667eea; border-bottom-color: #667eea; }
            
            /* 内容区域 */
            .tab-content { display: none; background: white; border-radius: 0 0 16px 16px; padding: 25px; box-shadow: 0 10px 40px rgba(0,0,0,0.15); margin-bottom: 30px; }
            .tab-content.show { display: block; }
            .content-title { font-size: 1.3rem; font-weight: 700; color: #333; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #f0f0f0; }
            
            /* 控制面板 */
            .control-panel { display: none; background: #f8f9fa; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
            .control-panel.show { display: block; }
            .control-row { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
            .control-label { font-weight: 600; color: #333; }
            .control-select { padding: 10px 15px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 1rem; cursor: pointer; }
            .control-select:focus { outline: none; border-color: #667eea; }
            .pagination { display: flex; align-items: center; gap: 10px; }
            .page-btn { background: #f0f0f0; border: none; padding: 10px 15px; border-radius: 8px; cursor: pointer; font-size: 1rem; transition: all 0.2s; }
            .page-btn:hover:not(:disabled) { background: #667eea; color: white; }
            .page-btn:disabled { opacity: 0.5; cursor: not-allowed; }
            .page-info { font-weight: 600; color: #333; min-width: 120px; text-align: center; }
            
            /* 图表网格 */
            .charts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(500px, 1fr)); gap: 25px; }
            .chart-card { background: white; border-radius: 16px; padding: 20px; border: 1px solid #e0e0e0; }
            .chart-title { font-size: 1.2rem; font-weight: 600; color: #333; margin-bottom: 15px; text-align: center; padding-bottom: 10px; border-bottom: 2px solid #f0f0f0; }
            .chart-container { height: 400px; position: relative; }
            
            /* 导出按钮 */
            .export-section { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; padding-bottom: 20px; border-bottom: 2px solid #f0f0f0; }
            .export-label { font-weight: 600; color: #333; }
            .export-btn { background: linear-gradient(135deg, #2ed573 0%, #26a65b 100%); color: white; border: none; padding: 10px 20px; border-radius: 8px; font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: all 0.2s; }
            .export-btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(46, 213, 115, 0.4); }
            .export-btn.secondary { background: linear-gradient(135deg, #ffa502 0%, #ff7f00 100%); }
            .export-btn.secondary:hover { box-shadow: 0 5px 15px rgba(255, 165, 2, 0.4); }
            
            /* 统计卡片 */
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
            .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 12px; text-align: center; }
            .stat-value { font-size: 2rem; font-weight: 700; }
            .stat-label { font-size: 0.9rem; opacity: 0.9; margin-top: 5px; }
            
            /* 数据表格 */
            .table-scroll { overflow-x: auto; border: 1px solid #e0e0e0; border-radius: 8px; }
            table { width: 100%; border-collapse: collapse; font-size: 0.95rem; min-width: 600px; }
            th { background: #f8f9fa; padding: 15px 12px; text-align: left; font-weight: 600; border-bottom: 2px solid #e0e0e0; white-space: nowrap; }
            td { padding: 12px; border-bottom: 1px solid #eee; }
            tr:hover { background: #f8f6ff; }
            .highlight { background: #fff3cd !important; font-weight: 600; }
            .action-btn { background: #667eea; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85rem; }
            
            /* 导出对话框 */
            .export-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.7); display: none; justify-content: center; align-items: center; z-index: 2000; }
            .export-overlay.show { display: flex; }
            .export-dialog { background: white; border-radius: 16px; padding: 30px; max-width: 500px; width: 90%; text-align: center; }
            .export-dialog h3 { font-size: 1.3rem; margin-bottom: 20px; }
            .export-options { display: flex; flex-direction: column; gap: 15px; max-height: 400px; overflow-y: auto; }
            .export-option { padding: 15px 20px; border: 2px solid #e0e0e0; border-radius: 10px; cursor: pointer; transition: all 0.2s; text-align: left; }
            .export-option:hover { border-color: #667eea; background: #f8f6ff; }
            .export-option h4 { font-size: 1rem; margin-bottom: 5px; color: #333; }
            .export-option p { font-size: 0.85rem; color: #666; }
            .export-close { margin-top: 20px; background: #f0f0f0; color: #333; border: none; padding: 10px 30px; border-radius: 8px; cursor: pointer; }
            .export-progress { margin-top: 20px; }
            .progress-bar { width: 100%; height: 10px; background: #f0f0f0; border-radius: 5px; overflow: hidden; }
            .progress-fill { height: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); transition: width 0.3s; }
            .progress-text { margin-top: 10px; font-size: 0.9rem; color: #666; }
            
            /* 长图导出 */
            .long-image-container { position: fixed; left: -9999px; top: 0; background: white; padding: 40px; }
            .long-image-header { text-align: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid #f0f0f0; }
            .long-image-header h2 { font-size: 1.5rem; color: #333; margin-bottom: 10px; }
            .long-image-header p { color: #666; }
            .long-image-grid { display: flex; flex-wrap: wrap; gap: 30px; justify-content: center; }
            .long-image-card { background: white; border: 1px solid #e0e0e0; border-radius: 12px; padding: 20px; width: 550px; }
            .long-image-card .chart-title { margin-bottom: 10px; }
            
            /* 提示框 */
            .toast { position: fixed; top: 20px; right: 20px; background: white; padding: 15px 25px; border-radius: 10px; box-shadow: 0 5px 30px rgba(0,0,0,0.2); display: none; z-index: 1000; animation: slideIn 0.3s ease; }
            .toast.show { display: block; }
            .toast.error { border-left: 4px solid #ff4757; }
            .toast.success { border-left: 4px solid #2ed573; }
            .toast.warning { border-left: #ffa502; }
            @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
            
            /* 加载动画 */
            .loading { display: none; text-align: center; padding: 50px; }
            .loading.show { display: block; }
            .spinner { width: 50px; height: 50px; border: 4px solid #f0f0f0; border-top: 4px solid #667eea; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 20px; }
            @keyframes spin { to { transform: rotate(360deg); } }
            
            /* 响应式 */
            @media (max-width: 768px) {
                .header h1 { font-size: 1.8rem; }
                .charts-grid { grid-template-columns: 1fr; }
                .control-row { flex-direction: column; align-items: flex-start; }
                .chart-container { height: 300px; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <!-- 头部 -->
            <div class="header">
                <h1>雷达图分析工具 (Chart.js)</h1>
                <p>上传数据文件，自动生成雷达图对比分析</p>
            </div>
            
            <!-- 上传区域 -->
            <div class="upload-section">
                <div class="upload-area" id="uploadArea">
                    <div class="upload-icon">📁</div>
                    <div class="upload-text">拖拽文件到此处或点击上传</div>
                    <div class="upload-hint">支持 CSV、XLSX、XLS 格式</div>
                    <input type="file" id="fileInput" accept=".csv,.xlsx,.xls">
                    <button class="upload-btn">选择文件</button>
                </div>
                
                <div class="file-info" id="fileInfo">
                    <div>
                        <div class="file-name" id="fileName">-</div>
                        <div class="file-stats" id="fileStats">-</div>
                    </div>
                    <button class="file-remove" onclick="removeFile()">移除</button>
                </div>
            </div>
            
            <!-- 加载动画 -->
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <div>正在处理数据...</div>
            </div>
            
            <!-- Tab 导航 -->
            <div class="tab-navigation" id="tabNavigation">
                <button class="tab-btn active" onclick="switchTab('preview')" id="tabPreview">数据预览</button>
                <button class="tab-btn" onclick="switchTab('charts')" id="tabCharts">雷达图分析</button>
                <button class="tab-btn" onclick="switchTab('data')" id="tabData">详细数据</button>
            </div>
            
            <!-- Tab 1: 数据预览 -->
            <div class="tab-content show" id="contentPreview">
                <h3 class="content-title">数据预览</h3>
                <div class="stats-grid" id="statsGrid"></div>
                <div class="table-scroll" id="previewTableWrapper">
                    <table id="previewTable"></table>
                </div>
            </div>
            
            <!-- Tab 2: 雷达图分析 -->
            <div class="tab-content" id="contentCharts">
                <h3 class="content-title">雷达图对比分析</h3>
                
                <!-- 导出按钮 -->
                <div class="export-section" id="exportSection">
                    <span class="export-label">导出方式:</span>
                    <button class="export-btn" onclick="showExportDialog('single')">导出单张图</button>
                    <button class="export-btn secondary" onclick="showExportDialog('long')">导出长图</button>
                    <button class="export-btn" onclick="exportMultipleCharts()">导出多张图</button>
                </div>
                
                <!-- 控制面板 -->
                <div class="control-panel show" id="controlPanel">
                    <div class="control-row">
                        <div>
                            <span class="control-label">每页显示:</span>
                            <select class="control-select" id="pageSize" onchange="changePageSize()">
                                <option value="1">1 个</option>
                                <option value="2">2 个</option>
                                <option value="4" selected>4 个</option>
                                <option value="6">6 个</option>
                                <option value="8">8 个</option>
                                <option value="12">12 个</option>
                                <option value="all">显示全部</option>
                            </select>
                        </div>
                        
                        <div class="pagination">
                            <button class="page-btn" id="prevBtn" onclick="prevPage()">上一页</button>
                            <span class="page-info" id="pageInfo">第 1 / 1 页</span>
                            <button class="page-btn" id="nextBtn" onclick="nextPage()">下一页</button>
                        </div>
                        
                        <div>
                            <span class="control-label">跳转到:</span>
                            <select class="control-select" id="jumpSelect" onchange="jumpToPage()"></select>
                        </div>
                    </div>
                </div>
                
                <div class="charts-grid" id="chartsGrid"></div>
            </div>
            
            <!-- Tab 3: 详细数据 -->
            <div class="tab-content" id="contentData">
                <h3 class="content-title">详细数据对比</h3>
                <div class="table-scroll">
                    <table id="dataTable"></table>
                </div>
            </div>
        </div>
        
        <!-- 导出对话框 -->
        <div class="export-overlay" id="exportOverlay">
            <div class="export-dialog">
                <h3 id="exportDialogTitle">选择要导出的雷达图</h3>
                <div class="export-options" id="exportOptions"></div>
                <div class="export-progress" id="exportProgress" style="display: none;">
                    <div class="progress-bar">
                        <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                    </div>
                    <div class="progress-text" id="progressText">准备导出...</div>
                </div>
                <button class="export-close" onclick="closeExportDialog()">关闭</button>
            </div>
        </div>
        
        <!-- 长图导出容器 -->
        <div class="long-image-container" id="longImageContainer">
            <div class="long-image-header">
                <h2 id="longImageTitle">雷达图对比分析</h2>
                <p id="longImageSubtitle"></p>
            </div>
            <div class="long-image-grid" id="longImageGrid"></div>
        </div>
        
        <!-- 提示框 -->
        <div class="toast" id="toast"></div>
        
        <script>
            // 全局变量
            let radarData = null;
            let currentPage = 1;
            let pageSize = 4;
            let charts = [];
            let currentFileName = '';
            
            // 初始化
            document.addEventListener('DOMContentLoaded', () => {
                setupUploadArea();
            });
            
            // 上传区域设置
            function setupUploadArea() {
                const uploadArea = document.getElementById('uploadArea');
                const fileInput = document.getElementById('fileInput');
                
                uploadArea.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    uploadArea.classList.add('dragover');
                });
                
                uploadArea.addEventListener('dragleave', () => {
                    uploadArea.classList.remove('dragover');
                });
                
                uploadArea.addEventListener('drop', (e) => {
                    e.preventDefault();
                    uploadArea.classList.remove('dragover');
                    if (e.dataTransfer.files.length > 0) {
                        handleFile(e.dataTransfer.files[0]);
                    }
                });
                
                fileInput.addEventListener('change', (e) => {
                    if (e.target.files.length > 0) {
                        handleFile(e.target.files[0]);
                    }
                });
            }
            
            // Tab 切换
            function switchTab(tabName) {
                document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
                document.getElementById('tab' + tabName.charAt(0).toUpperCase() + tabName.slice(1)).classList.add('active');
                
                document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('show'));
                document.getElementById('content' + tabName.charAt(0).toUpperCase() + tabName.slice(1)).classList.add('show');
                
                // 调整图表大小
                if (tabName === 'charts') {
                    setTimeout(() => {
                        charts.forEach(chart => chart.resize());
                    }, 100);
                }
            }
            
            // 处理文件
            async function handleFile(file) {
                const extension = file.name.split('.').pop().toLowerCase();
                if (!['csv', 'xlsx', 'xls'].includes(extension)) {
                    showToast('请上传 CSV、XLSX 或 XLS 格式的文件', 'error');
                    return;
                }
                
                showLoading(true);
                currentFileName = file.name.replace(/\\.[^/.]+$/, '');
                
                const formData = new FormData();
                formData.append('file', file);
                
                try {
                    const response = await fetch('/api/upload', { method: 'POST', body: formData });
                    const result = await response.json();
                    
                    if (!response.ok) throw new Error(result.detail);
                    
                    radarData = result;
                    displayFileInfo(file, result);
                    displayPreview(result);
                    generateChartsData();
                    renderDataTable();
                    
                    document.getElementById('tabNavigation').classList.add('show');
                    switchTab('preview');
                    showToast('文件上传成功！', 'success');
                    
                } catch (error) {
                    showToast(error.message, 'error');
                } finally {
                    showLoading(false);
                }
            }
            
            // 显示文件信息
            function displayFileInfo(file, result) {
                document.getElementById('fileName').textContent = file.name;
                document.getElementById('fileStats').textContent = '共 ' + result.validation.total_rows + ' 行 × ' + result.validation.total_columns + ' 列';
                document.getElementById('fileInfo').classList.add('show');
            }
            
            // 显示数据预览
            function displayPreview(result) {
                const data = result.data;
                
                // 统计卡片
                document.getElementById('statsGrid').innerHTML = 
                    '<div class="stat-card"><div class="stat-value">' + data.summary.total_rows + '</div><div class="stat-label">数据行数</div></div>' +
                    '<div class="stat-card"><div class="stat-value">' + data.summary.total_columns + '</div><div class="stat-label">分析维度</div></div>' +
                    '<div class="stat-card"><div class="stat-value">' + data.average.original.length + '</div><div class="stat-label">平均值数量</div></div>';
                
                // 预览表格
                let html = '<thead><tr><th>标签</th>';
                data.columns.forEach(col => { html += '<th>' + col + '</th>'; });
                html += '<th>操作</th></tr></thead><tbody>';
                
                data.rows.forEach((row, idx) => {
                    html += '<tr><td><strong>' + row.label + '</strong></td>';
                    row.original_values.forEach(val => { html += '<td>' + (typeof val === 'number' ? val.toFixed(2) : val) + '</td>'; });
                    html += '<td><button class="action-btn" onclick="viewChart(\\'' + row.label + '\\')">查看雷达图</button></td></tr>';
                });
                
                html += '<tr class="highlight"><td><strong>平均值</strong></td>';
                data.average.original.forEach(val => { html += '<td>' + val.toFixed(2) + '</td>'; });
                html += '<td>-</td></tr></tbody>';
                
                document.getElementById('previewTable').innerHTML = html;
            }
            
            // 生成雷达图数据
            function generateChartsData() {
                if (!radarData) return;
                currentPage = 1;
                
                const rowCount = radarData.data.rows.length;
                if (rowCount <= 6) {
                    pageSize = rowCount;
                    document.getElementById('pageSize').value = rowCount <= 8 ? String(rowCount) : '8';
                } else {
                    pageSize = 4;
                    document.getElementById('pageSize').value = '4';
                }
                
                updateJumpSelect();
                renderCharts();
            }
            
            // 更新跳转选择器
            function updateJumpSelect() {
                const totalPages = Math.ceil(radarData.data.rows.length / pageSize);
                const jumpSelect = document.getElementById('jumpSelect');
                jumpSelect.innerHTML = '';
                
                for (let i = 1; i <= totalPages; i++) {
                    jumpSelect.innerHTML += '<option value="' + i + '">第 ' + i + ' 页</option>';
                }
            }
            
            // 渲染图表
            function renderCharts() {
                const chartsGrid = document.getElementById('chartsGrid');
                const start = (currentPage - 1) * pageSize;
                const end = Math.min(start + pageSize, radarData.data.rows.length);
                const pageData = radarData.data.rows.slice(start, end);
                
                // 销毁旧图表
                charts.forEach(chart => chart.destroy());
                charts = [];
                chartsGrid.innerHTML = '';
                
                pageData.forEach((row, idx) => {
                    const card = document.createElement('div');
                    card.className = 'chart-card';
                    card.innerHTML = '<div class="chart-title">' + row.label + '</div><div class="chart-container"><canvas id="chart-' + idx + '"></canvas></div>';
                    chartsGrid.appendChild(card);
                    
                    setTimeout(() => { initChart(idx, row); }, 100);
                });
                
                updatePagination();
            }
            
            // 初始化单个雷达图
            function initChart(index, rowData) {
                const chartDom = document.getElementById('chart-' + index);
                if (!chartDom) return;
                
                const ctx = chartDom.getContext('2d');
                const data = radarData.data;
                
                const chart = new Chart(ctx, {
                    type: 'radar',
                    data: {
                        labels: data.columns,
                        datasets: [
                            {
                                label: rowData.label + ' (实际值)',
                                data: rowData.normalized_values,
                                backgroundColor: 'rgba(102, 126, 234, 0.4)',
                                borderColor: '#667eea',
                                borderWidth: 2,
                                pointBackgroundColor: '#667eea',
                                pointBorderColor: '#fff',
                                pointHoverBackgroundColor: '#fff',
                                pointHoverBorderColor: '#667eea'
                            },
                            {
                                label: '平均值',
                                data: data.average.normalized,
                                backgroundColor: 'rgba(255, 107, 107, 0.2)',
                                borderColor: '#ff6b6b',
                                borderWidth: 2,
                                borderDash: [5, 5],
                                pointBackgroundColor: '#ff6b6b',
                                pointBorderColor: '#fff',
                                pointHoverBackgroundColor: '#fff',
                                pointHoverBorderColor: '#ff6b6b'
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'bottom' },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const idx = context.dataIndex;
                                        const datasetIdx = context.datasetIndex;
                                        if (datasetIdx === 0) {
                                            const original = rowData.original_values[idx];
                                            const avg = data.average.original[idx];
                                            return context.dataset.label + ': ' + original.toFixed(2) + ' (平均: ' + avg.toFixed(2) + ')';
                                        } else {
                                            return context.dataset.label + ': ' + data.average.original[idx].toFixed(2);
                                        }
                                    }
                                }
                            }
                        },
                        scales: {
                            r: {
                                angleLines: { display: true },
                                suggestedMin: 0,
                                suggestedMax: 1,
                                ticks: {
                                    stepSize: 0.25,
                                    callback: function(value) { return (value * 100) + '%'; }
                                }
                            }
                        }
                    }
                });
                
                charts.push(chart);
            }
            
            // 渲染数据表格
            function renderDataTable() {
                const data = radarData.data;
                let html = '<thead><tr><th>标签</th>';
                data.columns.forEach(col => { html += '<th>' + col + '</th>'; });
                html += '<th>与平均值对比</th></tr></thead><tbody>';
                
                data.rows.forEach(row => {
                    const diff = row.original_values.map((v, i) => v - data.average.original[i]);
                    const avgDiff = diff.reduce((a, b) => a + b, 0) / diff.length;
                    const status = avgDiff > 0 ? '高于平均' : (avgDiff < 0 ? '低于平均' : '等于平均');
                    
                    html += '<tr><td><strong>' + row.label + '</strong></td>';
                    row.original_values.forEach((val, idx) => {
                        const diffVal = val - data.average.original[idx];
                        const color = diffVal > 0 ? '#2ed573' : (diffVal < 0 ? '#ff4757' : '#666');
                        const sign = diffVal > 0 ? '+' : '';
                        html += '<td style="color: ' + color + '">' + val.toFixed(2) + ' (' + sign + diffVal.toFixed(2) + ')</td>';
                    });
                    html += '<td>' + status + '</td></tr>';
                });
                
                html += '</tbody>';
                document.getElementById('dataTable').innerHTML = html;
            }
            
            // 查看雷达图
            function viewChart(label) {
                const idx = radarData.data.rows.findIndex(row => row.label === label);
                if (idx !== -1) {
                    currentPage = Math.floor(idx / pageSize) + 1;
                    switchTab('charts');
                    renderCharts();
                }
            }
            
            // 分页控制
            function prevPage() {
                if (currentPage > 1) {
                    currentPage--;
                    renderCharts();
                }
            }
            
            function nextPage() {
                const totalPages = Math.ceil(radarData.data.rows.length / pageSize);
                if (currentPage < totalPages) {
                    currentPage++;
                    renderCharts();
                }
            }
            
            function jumpToPage() {
                currentPage = parseInt(document.getElementById('jumpSelect').value);
                renderCharts();
            }
            
            function changePageSize() {
                const selectedValue = document.getElementById('pageSize').value;
                pageSize = selectedValue === 'all' ? radarData.data.rows.length : parseInt(selectedValue);
                currentPage = 1;
                updateJumpSelect();
                renderCharts();
            }
            
            function updatePagination() {
                const totalPages = Math.ceil(radarData.data.rows.length / pageSize);
                
                if (pageSize >= radarData.data.rows.length) {
                    document.getElementById('pageInfo').textContent = '共 ' + radarData.data.rows.length + ' 个';
                    document.getElementById('prevBtn').style.display = 'none';
                    document.getElementById('nextBtn').style.display = 'none';
                } else {
                    document.getElementById('pageInfo').textContent = '第 ' + currentPage + ' / ' + totalPages + ' 页';
                    document.getElementById('prevBtn').style.display = '';
                    document.getElementById('nextBtn').style.display = '';
                }
                
                document.getElementById('prevBtn').disabled = currentPage <= 1;
                document.getElementById('nextBtn').disabled = currentPage >= totalPages;
                document.getElementById('jumpSelect').value = currentPage;
            }
            
            // ==================== 导出功能 ====================
            
            function showExportDialog(type) {
                const overlay = document.getElementById('exportOverlay');
                const options = document.getElementById('exportOptions');
                const title = document.getElementById('exportDialogTitle');
                
                let html = '';
                
                if (type === 'single') {
                    title.textContent = '选择要导出的雷达图';
                    radarData.data.rows.forEach((row, idx) => {
                        html += '<div class="export-option" onclick="exportSingleChart(' + idx + ', \\'' + row.label + '\\')">' +
                            '<h4>' + row.label + '</h4><p>导出 ' + row.label + ' 的雷达图</p></div>';
                    });
                } else if (type === 'long') {
                    title.textContent = '导出长图';
                    html = '<div class="export-option" onclick="exportLongImage()">' +
                        '<h4>导出全部雷达图（长图）</h4><p>将所有雷达图合并为一张长图</p></div>';
                }
                
                options.innerHTML = html;
                overlay.classList.add('show');
            }
            
            function closeExportDialog() {
                document.getElementById('exportOverlay').classList.remove('show');
                document.getElementById('exportProgress').style.display = 'none';
            }
            
            async function exportSingleChart(index, label) {
                closeExportDialog();
                showToast('正在导出...', 'warning');
                
                try {
                    const targetPage = Math.floor(index / pageSize) + 1;
                    if (targetPage !== currentPage) {
                        currentPage = targetPage;
                        renderCharts();
                        await new Promise(r => setTimeout(r, 500));
                    }
                    
                    const chartIndex = index - (currentPage - 1) * pageSize;
                    if (chartIndex < 0 || chartIndex >= charts.length) throw new Error('图表未找到');
                    
                    const chart = charts[chartIndex];
                    const chartDom = document.getElementById('chart-' + chartIndex);
                    const chartCard = chartDom.closest('.chart-card');
                    
                    chart.resize();
                    await new Promise(r => setTimeout(r, 300));
                    
                    const canvas = await html2canvas(chartCard, { backgroundColor: '#ffffff', scale: 2, useCORS: true });
                    downloadImage(canvas.toDataURL('image/png'), label + '.png');
                    showToast('导出成功！', 'success');
                    
                } catch (error) {
                    showToast('导出失败: ' + error.message, 'error');
                }
            }
            
            async function exportLongImage() {
                closeExportDialog();
                showToast('正在生成长图...', 'warning');
                
                const progress = document.getElementById('exportProgress');
                const progressFill = document.getElementById('progressFill');
                const progressText = document.getElementById('progressText');
                
                progress.style.display = 'block';
                
                try {
                    const originalPageSize = pageSize;
                    pageSize = radarData.data.rows.length;
                    renderCharts();
                    
                    await new Promise(r => setTimeout(r, 1000));
                    
                    progressText.textContent = '正在渲染图表...';
                    progressFill.style.width = '30%';
                    
                    const container = document.getElementById('longImageContainer');
                    const grid = document.getElementById('longImageGrid');
                    
                    document.getElementById('longImageTitle').textContent = '雷达图对比分析';
                    document.getElementById('longImageSubtitle').textContent = '数据来源: ' + currentFileName;
                    
                    grid.innerHTML = '';
                    
                    for (let i = 0; i < radarData.data.rows.length; i++) {
                        const row = radarData.data.rows[i];
                        const card = document.createElement('div');
                        card.className = 'long-image-card';
                        card.innerHTML = '<div class="chart-title">' + row.label + '</div><div class="chart-container" id="export-chart-' + i + '" style="width: 500px; height: 400px;"></div>';
                        grid.appendChild(card);
                    }
                    
                    container.style.left = '0';
                    container.style.top = '0';
                    
                    await new Promise(r => setTimeout(r, 500));
                    
                    progressFill.style.width = '50%';
                    progressText.textContent = '正在初始化图表...';
                    
                    // 初始化导出图表
                    for (let i = 0; i < radarData.data.rows.length; i++) {
                        const row = radarData.data.rows[i];
                        const chartDom = document.getElementById('export-chart-' + i);
                        const ctx = chartDom.getContext('2d');
                        const data = radarData.data;
                        
                        new Chart(ctx, {
                            type: 'radar',
                            data: {
                                labels: data.columns,
                                datasets: [
                                    { label: row.label, data: row.normalized_values, backgroundColor: 'rgba(102, 126, 234, 0.4)', borderColor: '#667eea', borderWidth: 2 },
                                    { label: '平均值', data: data.average.normalized, backgroundColor: 'rgba(255, 107, 107, 0.2)', borderColor: '#ff6b6b', borderWidth: 2, borderDash: [5, 5] }
                                ]
                            },
                            options: { responsive: true, plugins: { legend: { position: 'bottom' } }, scales: { r: { suggestedMin: 0, suggestedMax: 1 } } } }
                        });
                        
                        progressFill.style.width = 50 + (i / radarData.data.rows.length) * 20 + '%';
                        progressText.textContent = '正在渲染图表 ' + (i + 1) + '/' + radarData.data.rows.length + '...';
                    }
                    
                    progressFill.style.width = '70%';
                    progressText.textContent = '正在生成图片...';
                    
                    const canvas = await html2canvas(container, { backgroundColor: '#ffffff', scale: 2, useCORS: true });
                    downloadImage(canvas.toDataURL('image/png'), currentFileName + '_雷达图.png');
                    
                    container.style.left = '-9999px';
                    pageSize = originalPageSize;
                    renderCharts();
                    
                    progressFill.style.width = '100%';
                    progressText.textContent = '导出完成！';
                    showToast('长图导出成功！', 'success');
                    
                    setTimeout(() => { progress.style.display = 'none'; }, 1500);
                    
                } catch (error) {
                    showToast('导出失败: ' + error.message, 'error');
                    progress.style.display = 'none';
                }
            }
            
            async function exportMultipleCharts() {
                showToast('正在导出多张图片...', 'warning');
                
                const progress = document.getElementById('exportProgress');
                const progressFill = document.getElementById('progressFill');
                const progressText = document.getElementById('progressText');
                
                progress.style.display = 'block';
                
                try {
                    const totalCharts = radarData.data.rows.length;
                    
                    for (let i = 0; i < totalCharts; i++) {
                        const row = radarData.data.rows[i];
                        
                        progressFill.style.width = ((i + 1) / totalCharts * 100) + '%';
                        progressText.textContent = '正在导出 ' + (i + 1) + '/' + totalCharts + ': ' + row.label;
                        
                        // 创建临时图表
                        const tempContainer = document.createElement('div');
                        tempContainer.style.cssText = 'position: fixed; left: -9999px; top: 0; width: 600px; height: 550px; background: white; padding: 20px; border-radius: 12px;';
                        tempContainer.innerHTML = '<div style="font-size: 1.3rem; font-weight: 600; text-align: center; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #f0f0f0; color: #333;">' + row.label + '</div><div style="width: 100%; height: 450px;"><canvas id="temp-chart-' + i + '"></canvas></div>';
                        document.body.appendChild(tempContainer);
                        
                        await new Promise(r => setTimeout(r, 100));
                        
                        const ctx = document.getElementById('temp-chart-' + i).getContext('2d');
                        const data = radarData.data;
                        
                        new Chart(ctx, {
                            type: 'radar',
                            data: {
                                labels: data.columns,
                                datasets: [
                                    { label: row.label, data: row.normalized_values, backgroundColor: 'rgba(102, 126, 234, 0.4)', borderColor: '#667eea', borderWidth: 2 },
                                    { label: '平均值', data: data.average.normalized, backgroundColor: 'rgba(255, 107, 107, 0.2)', borderColor: '#ff6b6b', borderWidth: 2, borderDash: [5, 5] }
                                ]
                            },
                            options: { responsive: false, plugins: { legend: { position: 'bottom' } }, scales: { r: { suggestedMin: 0, suggestedMax: 1 } } }
                        });
                        
                        await new Promise(r => setTimeout(r, 300));
                        
                        const canvas = await html2canvas(tempContainer, { backgroundColor: '#ffffff', scale: 2, useCORS: true });
                        downloadImage(canvas.toDataURL('image/png'), row.label + '.png');
                        
                        document.body.removeChild(tempContainer);
                        await new Promise(r => setTimeout(r, 500));
                    }
                    
                    progressFill.style.width = '100%';
                    progressText.textContent = '导出完成！';
                    showToast('成功导出 ' + totalCharts + ' 张图片！', 'success');
                    
                    setTimeout(() => { progress.style.display = 'none'; }, 1500);
                    
                } catch (error) {
                    showToast('导出失败: ' + error.message, 'error');
                    progress.style.display = 'none';
                }
            }
            
            function downloadImage(dataUrl, filename) {
                const link = document.createElement('a');
                link.download = filename;
                link.href = dataUrl;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }
            
            // 移除文件
            function removeFile() {
                radarData = null;
                currentPage = 1;
                charts = [];
                currentFileName = '';
                
                document.getElementById('fileInput').value = '';
                document.getElementById('fileInfo').classList.remove('show');
                document.getElementById('tabNavigation').classList.remove('show');
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('show'));
                document.getElementById('contentPreview').classList.add('show');
                document.getElementById('chartsGrid').innerHTML = '';
            }
            
            // 辅助函数
            function showLoading(show) {
                document.getElementById('loading').classList.toggle('show', show);
            }
            
            function showToast(message, type) {
                const toast = document.getElementById('toast');
                toast.textContent = message;
                toast.className = 'toast show ' + type;
                setTimeout(() => { toast.classList.remove('show'); }, 3000);
            }
        </script>
    </body>
    </html>
    """
    return html


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件并生成雷达图数据"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="请选择文件")
    
    content = await file.read()
    df = read_file(content, file.filename)
    validation = validate_data(df)
    radar_data = calculate_radar_data(df)
    
    return {
        "success": True,
        "filename": file.filename,
        "validation": validation,
        "data": radar_data
    }


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("[Radar Chart Tool - Chart.js版] Started")
    print("[URL] http://127.0.0.1:8002")
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8002)
