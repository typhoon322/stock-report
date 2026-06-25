"""
rotation/ci/github_comment.py — GitHub PR 评论自动发布

把 CI 报告写回 PR，实现"自动量化研究员 + 审计报告系统"
"""
import os, json, requests
from typing import Dict, Optional

def get_pr_number() -> Optional[int]:
    """从 GitHub Actions 环境获取 PR 编号"""
    # GitHub Actions event payload
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if event_path and os.path.exists(event_path):
        with open(event_path) as f:
            event = json.load(f)
        return event.get("pull_request", {}).get("number") or event.get("number")
    
    # 备选: GITHUB_REF
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/pull/"):
        parts = ref.split("/")
        if len(parts) >= 3:
            return int(parts[2])
    
    return None


def post_comment(body: str, pr_number: int = None) -> Dict:
    """
    将报告发布为 PR 评论
    
    Args:
        body: Markdown 格式的报告内容
        pr_number: PR编号 (不传则从环境变量获取)
    
    Returns:
        {"posted": bool, "status_code": int, "url": str}
    """
    if pr_number is None:
        pr_number = get_pr_number()
    
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    
    if not repo or not token:
        return {"posted": False, "error": "Missing GITHUB_REPOSITORY or GITHUB_TOKEN"}
    
    if not pr_number:
        return {"posted": False, "error": "No PR number found (not a PR event)"}
    
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    
    try:
        response = requests.post(url, json={"body": body}, headers=headers, timeout=15)
        result = {
            "posted": response.status_code == 201,
            "status_code": response.status_code,
            "url": response.json().get("html_url", "") if response.status_code == 201 else "",
        }
        if not result["posted"]:
            result["error"] = response.text[:200]
        return result
    except Exception as e:
        return {"posted": False, "error": str(e)}


def update_or_create_comment(body: str, pr_number: int = None, marker: str = "<!-- CI-REPORT -->") -> Dict:
    """
    幂等更新 PR 评论: 如果已有 CI 报告则更新，否则新建
    
    marker: 用于识别已有 CI 报告的标记
    """
    if pr_number is None:
        pr_number = get_pr_number()
    
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    
    if not repo or not token or not pr_number:
        return post_comment(body, pr_number)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    
    # 查找已有 CI 评论
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments?per_page=100"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            for comment in resp.json():
                if marker in comment.get("body", ""):
                    # 更新已有评论
                    update_url = f"https://api.github.com/repos/{repo}/issues/comments/{comment['id']}"
                    update_resp = requests.patch(update_url, json={"body": body}, headers=headers, timeout=10)
                    return {"posted": update_resp.status_code == 200, "updated": True, "status_code": update_resp.status_code}
    except:
        pass
    
    # 未找到旧评论 → 新建
    return post_comment(body, pr_number)
