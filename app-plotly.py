"""
雷达图分析工具 - Plotly 版本
使用 Plotly 生成雷达图，支持交互式 tooltip
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
import pandas as pd
import numpy as np
from io import BytesIO
import os
import plotly.graph_objects as go
import plotly.io as pio

app = FastAPI(title="雷达图分析工具 - Plotly版")

# 获取当前文件目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Plotly 配置
pio.templates.default = "plotly_white"


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


def generate_plotly_html(data: dict, filename: str) -> str:
    """生成 Plotly 雷达图 HTML"""
    
    indicators = data["indicators"]
    columns = data["columns"]
    rows = data["rows"]
    average = data["average"]
    
    # 创建雷达图
    fig = go.Figure()
    
    # 添加实际值线条（每个学生一行）
    colors = [
        '#667eea', '#ff6b6b', '#2ed573', '#ffa502', 
        '#1e90ff', '#e74c3c', '#9b59b6', '#3498db'
    ]
    
    for idx, row in enumerate(rows):
        # 自定义 hover 文本
        hover_texts = []
        for i, col in enumerate(columns):
            original = row["original_values"][i]
            avg = average["original"][i]
            diff = original - avg
            diff_str = f"+{diff:.2f}" if diff > 0 else f"{diff:.2f}"
            hover_texts.append(
                f"<b>{col}</b><br>" +
                f"实际值: {original:.2f}<br>" +
                f"平均值: {avg:.2f}<br>" +
                f"差值: {diff_str}"
            )
        
        fig.add_trace(go.Scatterpolar(
            r=row["normalized_values"],
            theta=columns,
            fill='toself',
            fillcolor=f'rgba{tuple(list(int(colors[idx % len(colors)].lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + [0.2])}',
            line=dict(color=colors[idx % len(colors)], width=2),
            name=row["label"],
            text=hover_texts,
            hoverinfo='text+name',
            marker=dict(size=8)
        ))
    
    # 添加平均值线条
    avg_hover_texts = []
    for i, col in enumerate(columns):
        avg = average["original"][i]
        avg_hover_texts.append(
            f"<b>{col}</b><br>" +
            f"平均值: {avg:.2f}"
        )
    
    fig.add_trace(go.Scatterpolar(
        r=average["normalized"],
        theta=columns,
        fill='toself',
        fillcolor='rgba(128, 128, 128, 0.2)',
        line=dict(color='rgba(128, 128, 128, 0.8)', width=2, dash='dash'),
        name='平均值',
        text=avg_hover_texts,
        hoverinfo='text+name',
        marker=dict(symbol='square', size=8)
    ))
    
    # 更新布局
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                tickvals=[0, 0.25, 0.5, 0.75, 1],
                ticktext=['0%', '25%', '50%', '75%', '100%']
            )
        ),
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=1.02
        ),
        title=dict(
            text=f"雷达图对比分析 - {filename}",
            x=0.5,
            font=dict(size=18)
        ),
        font=dict(family="Arial, sans-serif"),
        margin=dict(l=60, r=120, t=80, b=60),
        height=600,
        width=900
    )
    
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')


def generate_comparison_html(data: dict, filename: str) -> str:
    """生成多人对比雷达图 HTML"""
    
    columns = data["columns"]
    rows = data["rows"]
    average = data["average"]
    
    # 为每个人创建子图
    n_rows = len(rows)
    
    fig = go.Figure()
    
    colors = ['#667eea', '#ff6b6b', '#2ed573', '#ffa502']
    
    for idx, row in enumerate(rows):
        hover_texts = []
        for i, col in enumerate(columns):
            original = row["original_values"][i]
            avg = average["original"][i]
            hover_texts.append(
                f"<b>{col}</b><br>" +
                f"{row['label']}: {original:.2f}<br>" +
                f"平均: {avg:.2f}"
            )
        
        # 实际值
        fig.add_trace(go.Scatterpolar(
            r=row["normalized_values"],
            theta=columns,
            fill='toself',
            fillcolor=f'rgba{tuple(list(int(colors[idx % len(colors)].lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + [0.3])}',
            line=dict(color=colors[idx % len(colors)], width=2),
            name=f"{row['label']} 实际值",
            text=hover_texts,
            hoverinfo='text+name',
            marker=dict(size=8),
            subplot=f"polar{idx + 1}"
        ))
        
        # 平均值
        fig.add_trace(go.Scatterpolar(
            r=average["normalized"],
            theta=columns,
            line=dict(color='gray', width=2, dash='dash'),
            name=f"{row['label']} 平均值",
            hoverinfo='skip',
            marker=dict(symbol='square', size=6),
            subplot=f"polar{idx + 1}"
        ))
    
    # 更新布局
    n_cols = min(2, n_rows)
    n_rows_subplot = (n_rows + n_cols - 1) // n_cols
    
    fig.update_layout(
        title=dict(
            text=f"雷达图对比分析 - {filename}",
            x=0.5,
            font=dict(size=18)
        ),
        showlegend=True,
        font=dict(family="Arial, sans-serif"),
        height=300 * n_rows_subplot,
        width=900
    )
    
    # 更新每个子图
    for idx in range(1, n_rows + 1):
        fig.update_layout(**{f"polar{idx}": dict(
            domain=dict(x=[(idx - 1) % 2 * 0.5, (idx - 1) % 2 * 0.5 + 0.45], 
                       y=[1 - (idx - 1) // 2 * 0.5 - 0.45, 1 - (idx - 1) // 2 * 0.5]),
            radialaxis=dict(visible=True, range=[0, 1]),
            sector=[0, 360]
        )})
    
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')


@app.get("/", response_class=HTMLResponse)
async def home():
    """返回主页"""
    html = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>雷达图分析工具 - Plotly版本</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
            .container { max-width: 1200px; margin: 0 auto; }
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
            .chart-section { background: white; border-radius: 16px; padding: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.15); display: none; }
            .chart-section.show { display: block; }
            .loading { display: none; text-align: center; padding: 50px; }
            .loading.show { display: block; }
            .spinner { width: 50px; height: 50px; border: 4px solid #f0f0f0; border-top: 4px solid #667eea; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 20px; }
            @keyframes spin { to { transform: rotate(360deg); } }
            .file-info { margin-top: 20px; padding: 15px; background: #f0f9ff; border-radius: 10px; display: none; }
            .file-info.show { display: flex; align-items: center; justify-content: space-between; }
            .error { background: #fff3cd; padding: 15px; border-radius: 8px; color: #856404; margin-top: 15px; display: none; }
            .error.show { display: block; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>雷达图分析工具 (Plotly)</h1>
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
                <div id="chart"></div>
            </div>
        </div>
        
        <script>
            const fileInput = document.getElementById('fileInput');
            const fileInfo = document.getElementById('fileInfo');
            const fileName = document.getElementById('fileName');
            const fileStats = document.getElementById('fileStats');
            const loading = document.getElementById('loading');
            const chartSection = document.getElementById('chartSection');
            const chart = document.getElementById('chart');
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
                    
                    // 显示文件信息
                    fileName.textContent = result.filename;
                    fileStats.textContent = `共 ${result.validation.total_rows} 行 × ${result.validation.total_columns} 列`;
                    fileInfo.classList.add('show');
                    
                    // 生成图表
                    chart.innerHTML = result.html;
                    chartSection.classList.add('show');
                    
                } catch (error) {
                    errorMsg.textContent = error.message;
                    errorMsg.classList.add('show');
                } finally {
                    loading.classList.remove('show');
                }
            });
        </script>
    </body>
    </html>
    """
    return html


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件并生成雷达图"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="请选择文件")
    
    content = await file.read()
    df = read_file(content, file.filename)
    validation = validate_data(df)
    radar_data = calculate_radar_data(df)
    
    # 生成 Plotly HTML
    html = generate_plotly_html(radar_data, file.filename)
    
    return {
        "success": True,
        "filename": file.filename,
        "validation": validation,
        "html": html
    }


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("[Radar Chart Tool - Plotly版] Started")
    print("[URL] http://127.0.0.1:8003")
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8003)
