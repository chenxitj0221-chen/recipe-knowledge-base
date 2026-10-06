# 初始化本地 Git 仓库
git init

# 把本地仓库和云端仓库关联
git remote add origin https://github.com/chenxitj0221-chen/recipe-knowledge-base.git

# 把当前所有文件加入暂存区
git add .

# 提交第一次
git commit -m "初始化知识库结构"

# 推送到云端
git push -u origin main