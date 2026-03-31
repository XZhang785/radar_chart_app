"""
雷达图分析工具 - FastAPI 后端
支持上传 CSV/Excel 文件，生成雷达图对比数据与平均值
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pandas as pd
import numpy as np
from io import BytesIO, StringIO
import os

app = FastAPI(title="雷达图分析工具")

# 获取当前文件目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 挂载静态文件
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# 模板配置
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


def read_file(file_content: bytes, filename: str) -> pd.DataFrame:
    """
    根据文件扩展名读取文件并返回 DataFrame
    支持 .csv, .xlsx, .xls
    """
    file_extension = filename.lower().split('.')[-1]
    
    try:
        if file_extension == 'csv':
            # 尝试不同编码
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
    """
    验证数据格式：
    - 第一列应为行标识（标签列）
    - 其余列应为数值列（至少2列）
    """
    if df.shape[1] < 2:
        raise HTTPException(status_code=400, detail="数据至少需要2列（1列标签 + 1列数据）")
    
    if df.shape[0] < 2:
        raise HTTPException(status_code=400, detail="数据至少需要2行")
    
    # 检查数值列
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(numeric_cols) < 1:
        raise HTTPException(status_code=400, detail="数据中至少需要有1列数值数据")
    
    return {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "numeric_columns": len(numeric_cols)
    }


def calculate_radar_data(df: pd.DataFrame) -> dict:
    """
    计算雷达图数据
    - 第一列为标签列
    - 其余列为数值列
    - 计算每列的平均值
    """
    # 第一列作为行标签
    labels = df.iloc[:, 0].astype(str).tolist()
    
    # 其余列为数值数据
    data_df = df.iloc[:, 1:].select_dtypes(include=[np.number])
    columns = data_df.columns.tolist()
    
    if len(columns) == 0:
        raise HTTPException(status_code=400, detail="未找到数值列")
    
    # 计算每列平均值
    column_means = data_df.mean().tolist()
    
    # 转换为0-1比例（归一化）
    max_values = data_df.max()
    min_values = data_df.min()
    
    # 处理最大最小值相同的情况（避免除零）
    ranges = max_values - min_values
    ranges = ranges.replace(0, 1)  # 如果范围为0，设为1避免除零
    
    # 归一化数据（0-1范围）
    normalized_data = (data_df - min_values) / ranges
    
    # 归一化平均值
    normalized_means = [(column_means[i] - min_values.iloc[i]) / ranges.iloc[i] 
                        if ranges.iloc[i] != 0 else column_means[i] 
                        for i in range(len(column_means))]
    
    # 构建每行的雷达图数据
    rows_data = []
    for idx, label in enumerate(labels):
        row_values = normalized_data.iloc[idx].tolist()
        rows_data.append({
            "label": label,
            "original_values": data_df.iloc[idx].tolist(),  # 原始值
            "normalized_values": row_values
        })
    
    return {
        "indicators": [
            {
                "name": str(col),
                "max": 1.0,
                "min": 0.0
            } for col in columns
        ],
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
    """返回主页"""
    with open(os.path.join(BASE_DIR, "templates", "index.html"), "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    上传文件并生成雷达图数据
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="请选择文件")
    
    # 读取文件内容
    content = await file.read()
    
    # 读取数据
    df = read_file(content, file.filename)
    
    # 验证数据
    validation = validate_data(df)
    
    # 计算雷达图数据
    radar_data = calculate_radar_data(df)
    
    return {
        "success": True,
        "filename": file.filename,
        "validation": validation,
        "data": radar_data
    }


@app.post("/api/validate")
async def validate_file(file: UploadFile = File(...)):
    """
    仅验证文件格式，不生成完整数据
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="请选择文件")
    
    content = await file.read()
    df = read_file(content, file.filename)
    validation = validate_data(df)
    
    return {
        "success": True,
        "filename": file.filename,
        "validation": validation
    }


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("[Radar Chart Tool] Started successfully")
    print("[URL] http://127.0.0.1:8000")
    print("[Docs] http://127.0.0.1:8000/docs")
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8000)
