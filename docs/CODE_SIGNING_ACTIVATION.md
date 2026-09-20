# 正式代码签名启用清单

当前 V2.2 安装包通过 Defender 扫描，但尚未带受信任发布者签名。Chrome 或 Windows 可能因新文件信誉不足而阻止下载或提示“未知发布者”。自签名证书不能解决该问题。

## 一次性人工事项

1. 用卡嘴子实际经营主体（优先企业主体）申请受信任的 Windows 代码签名服务，并完成证件、联系人和付款验证。
2. 若选择 Microsoft Azure Artifact Signing，在 Azure 创建 Artifact Signing Account、Public Trust Certificate Profile，并完成身份验证。
3. 给 GitHub 仓库配置以下三项 Actions Secrets：`AZURE_CLIENT_ID`、`AZURE_TENANT_ID`、`AZURE_SUBSCRIPTION_ID`。不要把这些值发到聊天记录。
4. 给 GitHub 仓库配置以下四项 Actions Variables：
   - `KZ_ARTIFACT_SIGNING_ENABLED=true`
   - `KZ_ARTIFACT_SIGNING_ENDPOINT`，例如与你 Azure 区域一致的 `https://<region>.codesigning.azure.net/`
   - `KZ_ARTIFACT_SIGNING_ACCOUNT`
   - `KZ_ARTIFACT_SIGNING_PROFILE`
5. 在 Azure 为 GitHub 的联邦身份授予 **Artifact Signing Certificate Profile Signer** 角色。

## 已接入的自动流程

一旦以上配置齐全，GitHub 会在每次 V2.2 构建后自动：登录 Azure、对最终 EXE 使用 SHA-256 和 RFC 3161 时间戳签名、验证 Authenticode 签名、再执行 Defender 与安装测试，最后才发布 Release。

签名显示可信发布者并建立发布者信誉；但微软说明新证书也需要实际下载记录来积累 SmartScreen 信誉，不能承诺首次发布立即没有任何提示。
