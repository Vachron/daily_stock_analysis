# Skill: Backend Build

后端 Python 代码编译检查。

## 执行条件
- Python 3.10+
- 已安装依赖：`pip install -r requirements.txt`

## 执行命令

```bash
python -m py_compile <files...>
```

示例：
```bash
python -m py_compile src/core/screener_engine.py src/core/stock_pool.py
```

## 验收标准
- 退出码 0 表示通过
- 退出码非 0 表示语法错误

## 扩展用法

### 批量检查整个模块
```bash
python -m py_compile src/**/*.py
```

### 检查并报告错误
```bash
for f in $(git diff --name-only --staged | grep '\.py$'); do
    python -m py_compile "$f" || echo "FAILED: $f"
done
```

## 集成到 Agent 工作流

Coder Agent 在提交前必须对所有改动文件执行此检查。
