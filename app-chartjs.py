"""
雷达图分析工具 - Chart.js 版本
使用 Chart.js 作为前端渲染库
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
        "indicators": [{"name": str(col), "max": 1.0, "min": 0.0} for col in columns],
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
    """返回主页 - Chart.js 版本"""
    html = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>雷达图分析工具 - Chart.js版本</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
            .container { max-width: 1400px; margin: 0 auto; }
            .header { text-align: center; color: white; margin-bottom: 30px; }
            .header h1 { font-size: 2.5rem; margin-bottom: 10px; }
            .upload-section { background: white; border-radius: 16px; padding: 30px; margin-bottom: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.15); }
            .upload-area { border: 3px dashed #e0e0e0; border-radius: 12px; padding: 50px; text-align: center; cursor: pointer; transition: all 0.3s; }
            .upload-area:hover { border-color: #667eea; background: #f8f6ff; }
            .upload-icon { font-size: 4rem; margin-bottom: 15px; }
            .upload-text { font-size: 1.2rem; color: #666; margin-bottom: 10px; }
            .upload-hint { color: #999; }
            #fileInput { display: none; }
            .upload-btn { display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 30px; border-radius: 25px; font-size: 1rem; cursor: pointer; border: none; margin-top: 15px; }
            .file-info { margin-top: 20px; padding: 15px; background: #f0f9ff; border-radius: 10px; display: none; }
            .file-info.show { display: flex; align-items: center; justify-content: space-between; }
            .loading { display: none; text-align: center; padding: 50px; }
            .loading.show { display: block; }
            .spinner { width: 50px; height: 50px; border: 4px solid #f0f0f0; border-top: 4px solid #667eea; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 20px; }
            @keyframes spin { to { transform: rotate(360deg); } }
            .chart-section { background: white; border-radius: 16px; padding: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.15); display: none; margin-bottom: 30px; }
            .chart-section.show { display: block; }
            .chart-container { position: relative; height: 400px; margin: 20px 0; }
            .select-section { margin-bottom: 20px; display: flex; align-items: center; gap: 15px; }
            .select-label { font-weight: bold; }
            select { padding: 10px 15px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 1rem; cursor: pointer; }
            select:focus { outline: none; border-color: #667eea; }
            .data-table { margin-top: 30px; overflow-x: auto; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
            th { background: #f8f9fa; font-weight: 600; }
            tr:hover { background: #f8f6ff; }
            .error { background: #fff3cd; padding: 15px; border-radius: 8px; color: #856404; margin-top: 15px; display: none; }
            .error.show { display: block; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>雷达图分析工具 (Chart.js)</h1>
                <p>上传数据文件，自动生成雷达图对比分析</p>
            </div>
            
            <div class="upload-section">
                <div class="upload-area" onclick="document.getElementById('fileInput').click()">
                    <div class="upload-icon">📊</div>
                    <div class="upload-text">拖拽文件到此处或点击上传</div>
                    <div class="upload-hint">支持 CSV、XLSX、XLS 格式</div>
                    <input type="file" id="fileInput" accept=".csv,.xlsx,.xls">
                    <button class="upload-btn">选择文件</button>
                </div>
                
                <div class="file-info" id="fileInfo">
                    <span id="fileName"></span>
                    <span id="fileStats"></span>
                </div>
                
                <div class="error" id="errorMsg"></div>
            </div>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <div>正在处理数据...</div>
            </div>
            
            <div class="chart-section" id="chartSection">
                <h2>雷达图对比分析</h2>
                
                <div class="select-section">
                    <span class="select-label">选择学生:</span>
                    <select id="studentSelect" onchange="updateChart()">
                    </select>
                </div>
                
                <div class="chart-container">
                    <canvas id="radarChart"></canvas>
                </div>
                
                <div class="data-table" id="dataTable"></div>
            </div>
        </div>
        
        <script>
            let chart = null;
            let radarData = null;
            
            const fileInput = document.getElementById('fileInput');
            const fileInfo = document.getElementById('fileInfo');
            const fileName = document.getElementById('fileName');
            const fileStats = document.getElementById('fileStats');
            const loading = document.getElementById('loading');
            const chartSection = document.getElementById('chartSection');
            const studentSelect = document.getElementById('studentSelect');
            const errorMsg = document.getElementById('errorMsg');
            
            fileInput.addEventListener('change', async (e) => {
                const file = e.target.files[0];
                if (!file) return;
                
                loading.classList.add('show');
                errorMsg.classList.remove('show');
                
                const formData = new FormData();
                formData.append('file', file);
                
                try {
                    const response = await fetch('/api/upload', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    if (!response.ok) throw new Error(result.detail);
                    
                    fileName.textContent = result.filename;
                    fileStats.textContent = '共 ' + result.validation.total_rows + ' 行 × ' + result.validation.total_columns + ' 列';
                    fileInfo.classList.add('show');
                    
                    radarData = result.data;
                    initStudentSelect();
                    updateChart();
                    
                    chartSection.classList.add('show');
                    
                } catch (error) {
                    errorMsg.textContent = error.message;
                    errorMsg.classList.add('show');
                } finally {
                    loading.classList.remove('show');
                }
            });
            
            function initStudentSelect() {
                studentSelect.innerHTML = '';
                radarData.rows.forEach((row, idx) => {
                    const option = document.createElement('option');
                    option.value = idx;
                    option.textContent = row.label;
                    studentSelect.appendChild(option);
                });
            }
            
            function updateChart() {
                const idx = parseInt(studentSelect.value);
                const row = radarData.rows[idx];
                const columns = radarData.columns;
                const average = radarData.average;
                
                const colors = [
                    { bg: 'rgba(102, 126, 234, 0.4)', border: '#667eea' },
                    { bg: 'rgba(255, 107, 107, 0.4)', border: '#ff6b6b' }
                ];
                
                const datasets = [
                    {
                        label: row.label + ' (实际值)',
                        data: row.normalized_values,
                        backgroundColor: colors[0].bg,
                        borderColor: colors[0].border,
                        borderWidth: 2,
                        pointBackgroundColor: colors[0].border,
                        pointBorderColor: '#fff',
                        pointHoverBackgroundColor: '#fff',
                        pointHoverBorderColor: colors[0].border
                    },
                    {
                        label: '平均值',
                        data: average.normalized,
                        backgroundColor: colors[1].bg,
                        borderColor: colors[1].border,
                        borderWidth: 2,
                        borderDash: [5, 5],
                        pointBackgroundColor: colors[1].border,
                        pointBorderColor: '#fff',
                        pointHoverBackgroundColor: '#fff',
                        pointHoverBorderColor: colors[1].border
                    }
                ];
                
                if (chart) {
                    chart.destroy();
                }
                
                const ctx = document.getElementById('radarChart').getContext('2d');
                chart = new Chart(ctx, {
                    type: 'radar',
                    data: {
                        labels: columns,
                        datasets: datasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom'
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const idx = context.dataIndex;
                                        const original = context.datasetIndex === 0 
                                            ? row.original_values[idx] 
                                            : average.original[idx];
                                        return context.dataset.label + ': ' + original.toFixed(2);
                                    }
                                }
                            }
                        },
                        scales: {
                            r: {
                                angleLines: {
                                    display: true
                                },
                                suggestedMin: 0,
                                suggestedMax: 1,
                                ticks: {
                                    stepSize: 0.25,
                                    callback: function(value) {
                                        return (value * 100) + '%';
                                    }
                                }
                            }
                        }
                    }
                });
                
                // 更新数据表格
                updateDataTable(idx);
            }
            
            function updateDataTable(idx) {
                const row = radarData.rows[idx];
                const columns = radarData.columns;
                const average = radarData.average;
                
                let html = '<table><thead><tr><th>指标</th><th>实际值</th><th>平均值</th><th>差值</th></tr></thead><tbody>';
                
                columns.forEach((col, i) => {
                    const original = row.original_values[i];
                    const avg = average.original[i];
                    const diff = original - avg;
                    const diffClass = diff > 0 ? 'style="color: green"' : (diff < 0 ? 'style="color: red"' : '');
                    const diffText = diff > 0 ? '+' + diff.toFixed(2) : diff.toFixed(2);
                    
                    html += '<tr><td><strong>' + col + '</strong></td><td>' + original.toFixed(2) + '</td><td>' + avg.toFixed(2) + '</td><td ' + diffClass + '>' + diffText + '</td></tr>';
                });
                
                html += '</tbody></table>';
                document.getElementById('dataTable').innerHTML = html;
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
