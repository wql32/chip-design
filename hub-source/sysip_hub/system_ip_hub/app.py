from __future__ import annotations

import html
import json
import mimetypes
import os
import re
import shutil
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

from .catalog import Catalog
from .rtl_importer import make_draft, parse_rtl_file, scan_project


ROOT = Path(__file__).resolve().parent.parent
ASSET_ROOT = Path(os.environ.get("SYSTEM_IP_ASSET_ROOT", ROOT / "assets")).resolve()
DB_PATH = Path(os.environ.get("SYSTEM_IP_DB", ROOT / ".system_ip_hub" / "catalog.db")).resolve()
RTL_TEMPLATE_PATH = ROOT / "data" / "rtl_module_design_review_template.md"
AXI_SLICE_EXAMPLE_PATH = ROOT / "data" / "axi_channel_slice_design_review_example.md"
catalog = Catalog(ASSET_ROOT, DB_PATH)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


VERILOG_KEYWORDS = {
    "always", "always_comb", "always_ff", "always_latch", "assign", "automatic", "begin", "bind",
    "case", "casex", "casez", "class", "const", "constraint", "default", "disable", "else", "end",
    "endcase", "endclass", "endfunction", "endgenerate", "endmodule", "endpackage", "endprogram",
    "endproperty", "endspecify", "endsequence", "endtask", "endinterface", "for", "foreach", "force",
    "function", "generate", "genvar", "if", "ifdef", "ifndef", "import", "include", "interface", "join",
    "localparam", "logic", "module", "negedge", "or", "package", "parameter", "posedge", "program",
    "property", "release", "repeat", "return", "sequence", "signed", "specify", "static", "struct",
    "task", "typedef", "union", "unique", "unsigned", "until", "wait", "while", "wire", "with",
}


def highlight_verilog(source: str) -> str:
    """Return line-wrapped, escaped Verilog/SystemVerilog with lightweight highlighting."""
    lines: list[str] = []
    in_block_comment = False
    for raw_line in source.splitlines() or [""]:
        line: list[str] = []
        index = 0
        while index < len(raw_line):
            if in_block_comment:
                end = raw_line.find("*/", index)
                if end < 0:
                    line.append(f'<span class="tok-comment">{esc(raw_line[index:])}</span>')
                    index = len(raw_line)
                else:
                    line.append(f'<span class="tok-comment">{esc(raw_line[index:end + 2])}</span>')
                    index = end + 2
                    in_block_comment = False
                continue
            if raw_line.startswith("//", index):
                line.append(f'<span class="tok-comment">{esc(raw_line[index:])}</span>')
                break
            if raw_line.startswith("/*", index):
                end = raw_line.find("*/", index + 2)
                if end < 0:
                    line.append(f'<span class="tok-comment">{esc(raw_line[index:])}</span>')
                    in_block_comment = True
                    break
                line.append(f'<span class="tok-comment">{esc(raw_line[index:end + 2])}</span>')
                index = end + 2
                continue
            char = raw_line[index]
            if char == '"':
                end = index + 1
                while end < len(raw_line):
                    if raw_line[end] == '"' and raw_line[end - 1] != "\\":
                        end += 1
                        break
                    end += 1
                line.append(f'<span class="tok-string">{esc(raw_line[index:end])}</span>')
                index = end
                continue
            if char == "`":
                match = re.match(r"`[A-Za-z_]\w*", raw_line[index:])
                if match:
                    line.append(f'<span class="tok-directive">{esc(match.group(0))}</span>')
                    index += len(match.group(0))
                    continue
            identifier = re.match(r"[A-Za-z_]\w*", raw_line[index:])
            if identifier:
                value = identifier.group(0)
                cls = "tok-keyword" if value in VERILOG_KEYWORDS else "tok-identifier"
                line.append(f'<span class="{cls}">{esc(value)}</span>')
                index += len(value)
                continue
            number = re.match(r"(?:\d+'[sS]?[bBoOdDhH][0-9a-fA-F_xz?]+|\d+(?:\.\d+)?|\$[A-Za-z_]\w*)", raw_line[index:])
            if number:
                value = number.group(0)
                line.append(f'<span class="tok-number">{esc(value)}</span>')
                index += len(value)
                continue
            line.append(esc(char))
            index += 1
        lines.append(f"<span class='source-line'>{''.join(line) or ' '}</span>")
    return "\n".join(lines)


STATUS_META = {
    "ready": ("Ready", "可直接复用", "ok"),
    "stable": ("Ready", "可直接复用", "ok"),
    "simulation_checked": ("Ready", "可直接复用", "ok"),
    "constrained": ("Constrained", "满足约束后复用", "info"),
    "needs_fix": ("Needs Fix", "修复后再复用", "danger"),
    "draft": ("Draft", "设计草稿", "warn"),
    "experimental": ("Experimental", "实验性实现", "warn"),
    "deprecated": ("Deprecated", "不再推荐", "muted"),
}

PATTERN_GUIDE: dict[str, tuple[str, list[str]]] = {
    "burst-boundary-splitting": ("在协议边界、最大 burst 长度或目标宽度约束处拆分事务，同时保持地址、长度和响应关系。", ["边界地址和剩余长度计算", "拆分后的 LAST、响应和错误合并", "禁止生成零长度子事务"]),
    "clock-domain crossing": ("使用同步器、握手或异步 FIFO 在不同时钟域之间传递控制或数据。", ["信号类型决定同步结构", "复位释放与亚稳态约束", "多 bit 数据一致性"]),
    "command-data-path-separation": ("将命令控制与大位宽数据路径解耦，分别处理排队、反压和完成条件。", ["命令与数据重新配对", "异常和取消路径", "两条路径的容量匹配"]),
    "credit-based-flow-control": ("用 credit 表示下游可接收资源，发送与归还事件共同维护可用额度。", ["增减同周期优先级", "overflow/underflow 防护", "复位和错误恢复时的额度重建"]),
    "decoupled-ready-valid": ("使用 ready/valid 解耦生产者和消费者，使双方只在握手周期推进状态。", ["反压期间 payload 稳定", "valid 不依赖 ready", "避免组合环路"]),
    "elastic-buffer": ("以一到两级寄存缓冲吸收反压并切断 ready/valid 长组合路径。", ["满边界同时出入", "吞吐是否产生气泡", "复位清除有效位"]),
    "fifo buffering": ("用读写指针和容量状态保存有序事务，隔离生产与消费速率差。", ["空满边界", "指针回绕", "同周期读写和非法操作"]),
    "one-hot encoding": ("使用 one-hot 选择降低局部译码复杂度，并在边界处转换为二进制索引。", ["全零输入语义", "multi-hot 优先级或报错", "位宽为 1 和非 2 的幂"]),
    "resource-counter": ("用计数器或 bitmap 跟踪 tag、entry、credit 等有限资源的占用与释放。", ["重复释放和重复分配", "计数与真实集合一致", "同周期申请释放"]),
    "round-robin arbitration": ("从上次服务位置之后开始搜索请求，使持续请求源获得无饥饿轮询服务。", ["只在 grant 被接受后推进", "反压期间 grant 稳定性", "复位后的首次优先级"]),
    "state storage": ("使用寄存器阵列、RAM 或 CAM 保存小容量状态，并明确读写冲突和有效位语义。", ["同址读写策略", "未初始化项", "地址越界和清除优先级"]),
    "transaction-lifecycle": ("显式记录事务从分配、发出、等待响应到释放资源的完整生命周期。", ["每个状态的唯一归属", "超时与错误退出", "响应和资源释放只发生一次"]),
    "watchdog": ("为可能长期等待的事务设置计时和超时事件，避免资源永久占用。", ["超时边界定义", "正常完成与超时同周期", "超时后的清理和上报"]),
}

PROBLEM_GUIDE: dict[str, tuple[str, list[str]]] = {
    "4kb boundary": ("AXI burst 不得跨越 4KB 边界，桥接和 DMA 路径必须在边界前拆分。", ["起始地址接近 4KB 尾部", "非对齐地址", "拆分后响应合并"]),
    "backpressure": ("下游撤销 ready 时，上游必须停止推进并保持当前事务信息稳定。", ["valid/payload 稳定", "内部容量不会溢出", "解除反压后无丢失重复"]),
    "burst length": ("源协议和目标协议的最大 burst 长度不同，转换时需要正确分段。", ["长度编码的 off-by-one", "最后一个 beat", "多个子 burst 的完成条件"]),
    "credit leak": ("事务完成或异常退出后未归还 credit，最终导致系统永久停止发送。", ["所有退出路径归还一次", "超时/错误路径", "复位后的重建"]),
    "credit overflow": ("重复归还或错误初始化使 credit 超过资源上限，可能造成资源重复使用。", ["上限饱和或断言", "重复 completion", "增减同周期"]),
    "cxl/axi ordering and coherency policy": ("CXL 与 AXI 的顺序、可见性和一致性语义并不天然等价，需要显式转换策略。", ["同地址顺序", "posted/non-posted 完成", "cache/coherency 属性映射"]),
    "error recovery": ("错误或超时发生后，控制状态、资源和上游响应必须形成可恢复的闭环。", ["只上报一次", "释放全部关联资源", "迟到响应的处理"]),
    "fairness, starvation and grant timing": ("仲裁器可能因推进条件或 grant 保持错误导致请求长期得不到服务。", ["持续请求无饥饿", "仅接受后推进", "反压期间请求变化"]),
    "fifo boundary, reset and overflow behavior": ("FIFO 的空满边界、指针回绕和复位行为是最常见的数据损坏来源。", ["满时写和空时读", "满边界同时读写", "复位时内部有效状态"]),
    "invalid one-hot input and priority behavior": ("one-hot 输入全零或 multi-hot 时若没有定义，会产生地址 0 歧义或数据 OR 合并。", ["增加 valid", "定义优先方向", "增加 onehot0 断言"]),
    "outstanding limit": ("发出事务数量超过 tag、credit 或目标 outstanding 能力会覆盖状态或造成死锁。", ["发出条件统一门控", "计数与 tag 集合一致", "返回乱序"]),
    "pcie completion ordering and tag tracking": ("PCIe completion 可能乱序返回，必须按 tag 和字节范围匹配原请求。", ["split completion", "错误 completion", "tag 回收时机"]),
    "read/write collision and state retention": ("同一存储项的并发读写、清除和搜索若优先级不明确会产生不确定结果。", ["定义 read-first/write-first", "有效位与数据同步", "组合输出完整赋值"]),
    "ready-valid timing": ("ready/valid 组合路径过长或形成环路会限制频率并导致接口难以收敛。", ["切断 ready 长路径", "保持满吞吐", "边界气泡"]),
    "ready/valid backpressure and channel independence": ("AXI 各通道独立反压，错误地绑定 AW/W 或 AR/R 会造成死锁。", ["各通道独立推进", "sideband 与 valid 同步", "跨通道状态容量"]),
    "request timeout": ("请求在限定周期内未完成，需要生成可定位的超时事件。", ["计数起止点", "完成与超时同周期", "阈值为 0/1"]),
    "reset release and cross-domain synchronization": ("异步复位释放或两个域恢复顺序不一致，可能产生伪脉冲和握手状态分裂。", ["各域同步释放", "单边复位恢复", "同步链属性与约束"]),
    "stuck transaction": ("事务因响应丢失、credit 泄漏或状态机遗漏而永久停留在处理中。", ["watchdog 覆盖每个等待状态", "暴露事务上下文", "安全清理策略"]),
    "unaligned transfer": ("非对齐地址会影响首尾 byte-enable、beat 数量和边界拆分。", ["首 beat 偏移", "尾 beat mask", "与 4KB/最大长度同时发生"]),
}


def status_info(status: object) -> tuple[str, str, str]:
    value = str(status or "draft")
    return STATUS_META.get(value, (value, value, "muted"))


def _inline_markdown(value: str) -> str:
    rendered = esc(value)
    rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
    rendered = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", rendered)
    return rendered


def _heading_id(value: str, used: set[str]) -> str:
    base = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value.lower()).strip("-") or "section"
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}-{index}"
        index += 1
    used.add(candidate)
    return candidate


def render_markdown(content: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Render the deliberately small Markdown subset used by asset READMEs."""
    lines = content.replace("\r\n", "\n").split("\n")
    output: list[str] = []
    toc: list[tuple[int, str, str]] = []
    used_ids: set[str] = set()
    list_type = ""
    in_fence = False
    fence_lines: list[str] = []
    fence_language = ""

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            output.append(f"</{list_type}>")
            list_type = ""

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```"):
            close_list()
            if in_fence:
                language = f" data-language='{esc(fence_language)}'" if fence_language else ""
                output.append(f"<pre class='md-code'{language}><code>{esc(chr(10).join(fence_lines))}</code></pre>")
                fence_lines = []
                fence_language = ""
                in_fence = False
            else:
                in_fence = True
                fence_language = stripped[3:].strip()
            index += 1
            continue
        if in_fence:
            fence_lines.append(line)
            index += 1
            continue
        if not stripped:
            close_list()
            index += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            close_list()
            level = len(heading.group(1))
            label = heading.group(2).strip()
            anchor = _heading_id(label, used_ids)
            output.append(f"<h{level} id='{esc(anchor)}'>{_inline_markdown(label)}</h{level}>")
            if 2 <= level <= 3:
                toc.append((level, label, anchor))
            index += 1
            continue

        if index + 1 < len(lines) and "|" in line and re.match(r"^\s*\|?\s*:?-{3,}", lines[index + 1]):
            close_list()
            headers = [cell.strip() for cell in line.strip().strip("|").split("|")]
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append([cell.strip() for cell in lines[index].strip().strip("|").split("|")])
                index += 1
            head_html = "".join(f"<th>{_inline_markdown(cell)}</th>" for cell in headers)
            row_html = "".join("<tr>" + "".join(f"<td>{_inline_markdown(cell)}</td>" for cell in row) + "</tr>" for row in rows)
            output.append(f"<div class='md-table-wrap'><table><thead><tr>{head_html}</tr></thead><tbody>{row_html}</tbody></table></div>")
            continue

        unordered = re.match(r"^[-*]\s+(.+)$", stripped)
        ordered = re.match(r"^\d+\.\s+(.+)$", stripped)
        if unordered or ordered:
            wanted = "ul" if unordered else "ol"
            if list_type != wanted:
                close_list()
                list_type = wanted
                output.append(f"<{wanted}>")
            output.append(f"<li>{_inline_markdown((unordered or ordered).group(1))}</li>")
            index += 1
            continue

        close_list()
        if stripped.startswith(">"):
            output.append(f"<blockquote>{_inline_markdown(stripped.lstrip('>').strip())}</blockquote>")
        else:
            output.append(f"<p>{_inline_markdown(stripped)}</p>")
        index += 1

    close_list()
    if in_fence:
        output.append(f"<pre class='md-code'><code>{esc(chr(10).join(fence_lines))}</code></pre>")
    return "".join(output), toc


def read_asset_readme(root: Path) -> tuple[str, Path | None]:
    for name in ("README.md", "readme.md", "Readme.md"):
        candidate = root / name
        if candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8"), candidate
            except UnicodeDecodeError:
                return "", candidate
    return "", None


def current_conclusion(content: str) -> str:
    lines = content.replace("\r\n", "\n").split("\n")
    capture = False
    result: list[str] = []
    for line in lines:
        if re.match(r"^##\s+当前结论\s*$", line.strip(), re.IGNORECASE):
            capture = True
            continue
        if capture and re.match(r"^#{1,6}\s+", line.strip()):
            break
        if capture and line.strip():
            result.append(re.sub(r"[`*_]", "", line.strip()))
        elif capture and result:
            break
    return " ".join(result)


def is_sample_asset(asset: dict[str, object]) -> bool:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    name = f"{asset.get('name', '')} {asset.get('display_name', '')}".lower()
    return bool(metadata.get("sample")) or "sample" in name or "示例" in name


def asset_search_text(asset: dict[str, object]) -> str:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    values: list[str] = [
        str(asset.get("name", "")),
        str(asset.get("display_name", "")),
        str(asset.get("description", "")),
        str(asset.get("category", "")),
    ]
    for field in ("tags", "features", "design_patterns", "problem_index", "limitations"):
        field_values = metadata.get(field) if isinstance(metadata.get(field), list) else []
        values.extend(str(item) for item in field_values)
    root = Path(str(asset.get("root_path", "")))
    readme, _path = read_asset_readme(root)
    values.append(readme)
    return "\n".join(values).lower()


def snapshot_data(kind: str, entries: list[dict[str, object]]) -> str:
    # JSON lives in an HTML script element; literal '<' could close it early.
    payload = json.dumps({"kind": kind, "entries": entries}, ensure_ascii=False).replace("<", "\\u003c")
    return f"<script id='snapshot-data' type='application/json'>{payload}</script>"


def page(title: str, body: str) -> bytes:
    content = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} - System IP Design Hub</title>
<style>
:root{{--ink:#132238;--muted:#62758a;--line:#d8e4ef;--panel:#ffffff;--nav:#081525;--blue:#2f80ed;--cyan:#19bfd2;--green:#0f9d72;--amber:#c77900;--violet:#7357d9;}}
*{{box-sizing:border-box}} [hidden]{{display:none!important}} .snapshot-only{{display:none}} body{{font-family:Segoe UI,Inter,Arial,sans-serif;background:#eef4fa;color:var(--ink);margin:0;min-height:100vh;background-image:linear-gradient(rgba(38,93,140,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(38,93,140,.035) 1px,transparent 1px);background-size:28px 28px}}
.skip-link{{position:fixed;left:16px;top:-60px;z-index:100;background:#fff;color:#0c5f91;padding:10px 14px;border-radius:8px;box-shadow:0 6px 20px #0003}} .skip-link:focus{{top:12px}} :focus-visible{{outline:3px solid #36bfd0;outline-offset:2px}} button,a,input,select,textarea{{transition:border-color .16s ease,background-color .16s ease,box-shadow .16s ease,transform .16s ease}}
header{{background:linear-gradient(115deg,#071322 0%,#0d2947 57%,#10495a 100%);color:white;padding:14px 34px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 10px 30px #102a4330;position:sticky;top:0;z-index:5;border-bottom:1px solid #55d6e126}}
.brand{{display:flex;align-items:center;gap:11px}} .brand-mark{{width:29px;height:29px;border:1px solid #5de0ef80;border-radius:8px;display:grid;place-items:center;background:#1bc8da16;box-shadow:0 0 20px #1bc8da22}} .brand-mark:before{{content:"";width:10px;height:10px;border:2px solid #6be5ef;border-radius:3px;box-shadow:7px 0 0 -4px #6be5ef,-7px 0 0 -4px #6be5ef}} .brand-copy{{display:flex;flex-direction:column;gap:1px}} .brand-copy small{{font:10px Consolas,monospace;color:#72d9e4;letter-spacing:1.4px}} header .nav{{color:#fff;font-size:16px;letter-spacing:.2px;font-weight:650}} header nav{{display:flex;gap:4px;flex-wrap:wrap;align-items:center}} header a{{color:#c9e7f5;text-decoration:none;padding:8px 11px;border-radius:8px;font-size:13px}} header nav a:hover{{background:#ffffff18;color:white;box-shadow:inset 0 0 0 1px #72d9e430}}
main{{max-width:1320px;margin:38px auto;padding:0 28px}} h1{{font-size:32px;letter-spacing:-.7px;margin:0 0 8px}} h2{{margin-top:0}} h3{{margin-top:0}} .eyebrow{{color:var(--cyan);font:700 11px Consolas,monospace;text-transform:uppercase;letter-spacing:1.9px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px}} .stat-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin:22px 0}}
.card{{background:linear-gradient(145deg,#fff,#f8fbfe);border:1px solid var(--line);border-radius:15px;padding:21px;box-shadow:0 8px 24px #173b5d0c}} .card:hover{{box-shadow:0 12px 28px #173b5d16;transition:.18s ease}}
.stat-card{{position:relative;overflow:hidden}} .stat-card:after{{content:"";position:absolute;right:-28px;top:-28px;width:88px;height:88px;border-radius:50%;background:#2f80ed12}} .stat-value{{font-size:30px;font-weight:750;margin-top:8px}} .stat-label{{color:var(--muted);font-size:13px}}
.muted{{color:var(--muted)}} .pill{{display:inline-block;background:#e6f2fb;color:#17648a;border:1px solid #c7e5f0;border-radius:999px;padding:5px 10px;margin:2px;font-size:12px;font-weight:600}}
table{{width:100%;border-collapse:separate;border-spacing:0;background:var(--panel);border:1px solid var(--line);border-radius:13px;overflow:hidden;box-shadow:0 5px 18px #173b5d0a}} th,td{{padding:14px 15px;border-bottom:1px solid #e8eef5;text-align:left;vertical-align:top}} th{{background:#f2f7fb;color:#506176;font-size:11px;text-transform:uppercase;letter-spacing:.7px}} tr:last-child td{{border-bottom:0}} table tr:hover td{{background:#f7fbff}}
a{{color:#1769aa}} code,pre{{font-family:Consolas,"Cascadia Code",monospace}} code{{color:#135d83}} pre{{background:#0b172a;color:#dcebf7;padding:18px;border-radius:12px;overflow:auto;white-space:pre-wrap;line-height:1.5;border:1px solid #1d4260}}
input,select,textarea,button{{padding:10px 12px;border:1px solid #c8d7e5;border-radius:8px;background:white;font:inherit}} input{{min-width:210px}} textarea{{width:100%;min-height:110px;resize:vertical}} button{{cursor:pointer;background:linear-gradient(135deg,#2377dd,#1359af);color:white;border-color:#1a63bd;font-weight:650;box-shadow:0 4px 10px #185abd24}} button:hover{{filter:brightness(1.08)}} form{{display:flex;gap:9px;flex-wrap:wrap;margin:18px 0}}
.toolbar{{display:flex;justify-content:space-between;gap:14px;align-items:center;flex-wrap:wrap;margin:20px 0}} .section-title{{display:flex;align-items:center;gap:10px;margin:26px 0 12px}} .section-title:before{{content:"";width:4px;height:20px;border-radius:4px;background:linear-gradient(#18b6c9,#2f80ed)}}
.hero{{background:linear-gradient(120deg,#091a2d,#103a56 62%,#105265);color:white;border:1px solid #2a6680;border-radius:19px;padding:32px;box-shadow:0 18px 40px #0b254333;position:relative;overflow:hidden}} .hero:before{{content:"";position:absolute;inset:0;background:linear-gradient(105deg,transparent 0 58%,#6be5ef0b 58% 58.3%,transparent 58.3% 100%),linear-gradient(90deg,transparent 0 75%,#6be5ef0b 75% 75.15%,transparent 75.15% 100%);pointer-events:none}} .hero:after{{content:"SYS / IP";position:absolute;right:26px;bottom:18px;font:700 50px Consolas;color:#ffffff0a;letter-spacing:5px}} .hero p{{color:#b8d5e7;max-width:730px}} .hero .eyebrow{{color:#64d7e4}}
.hero h1{{max-width:720px;font-size:36px;line-height:1.15;margin-top:12px}} .hero-actions{{display:flex;align-items:center;gap:18px;margin-top:25px;position:relative;z-index:1}} .hero-button{{background:#73e1e8;color:#092237;padding:10px 15px;border-radius:8px;text-decoration:none;font-weight:750;box-shadow:0 6px 18px #02152244}} .hero-button:hover{{background:#a0f0f2;color:#092237}} .hero-link{{color:#bdeaf0;text-decoration:none;font-weight:650}} .hero-link:hover{{color:white}}
.dashboard-links .link-card{{text-decoration:none;color:var(--ink);position:relative}} .link-card h3{{margin:9px 0 5px}} .link-card p{{color:var(--muted);margin:0 0 14px}} .link-card>span:last-child{{color:#1769aa;font-weight:700;font-size:13px}} .link-card:hover{{border-color:#9ed8e4}}
.result-line{{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap;margin:18px 0 12px;font-size:13px}} .category-label{{font:600 12px Consolas,monospace;color:#526d84;background:#eef4f8;border:1px solid #d5e3ec;border-radius:6px;padding:5px 8px}}
.filter-panel{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:15px;margin:20px 0 14px;box-shadow:0 6px 18px #173b5d0a}} .filter-panel form{{margin:0;display:grid;grid-template-columns:minmax(240px,2fr) repeat(4,minmax(130px,1fr)) auto;gap:9px}} .filter-panel input,.filter-panel select{{min-width:0;width:100%}} .filter-footer{{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-top:12px;padding-top:12px;border-top:1px solid #e7eef4}} .scope-switch,.view-switch{{display:flex;gap:5px;flex-wrap:wrap}} .scope-switch a,.view-switch a{{padding:6px 10px;border-radius:7px;text-decoration:none;color:#547087;font-size:12px;font-weight:700}} .scope-switch a.active,.view-switch a.active{{background:#e6f3fa;color:#0b6492}} .clear-filter{{font-size:13px;text-decoration:none}}
.asset-card-list{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:13px}} .asset-list-card{{display:grid;grid-template-columns:1fr auto;gap:12px;background:#fff;border:1px solid var(--line);border-radius:13px;padding:18px;text-decoration:none;color:var(--ink)}} .asset-list-card:hover{{border-color:#8ec8dc;box-shadow:0 9px 24px #173b5d13;transform:translateY(-1px)}} .asset-list-card h3{{margin:0 0 4px;font-size:17px}} .asset-list-card p{{margin:8px 0 0;color:var(--muted);font-size:13px;line-height:1.55}} .asset-list-card .meta{{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:10px}} .asset-table-name p{{margin:5px 0 0;max-width:600px;color:var(--muted);font-size:12px;line-height:1.45}} .sample-mark{{display:inline-block;background:#f0eafe;color:#6c48b5;border:1px solid #d9cbf5;border-radius:999px;padding:3px 7px;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.5px}}
.knowledge-list{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}} .knowledge-card{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:20px;box-shadow:0 7px 20px #173b5d0b;display:flex;flex-direction:column;min-height:230px}} .knowledge-card header{{position:static;background:none;color:inherit;padding:0;box-shadow:none;border:0;display:flex;align-items:flex-start;justify-content:space-between;gap:15px}} .knowledge-card h2{{font-size:18px;margin:0;line-height:1.35}} .knowledge-card>p{{color:#52677a;line-height:1.65;font-size:14px;flex:1}} .knowledge-card .asset-links{{padding-top:13px;border-top:1px solid #e6edf3}} .knowledge-card .asset-links strong{{display:block;font-size:12px;color:#5c7082;margin-bottom:7px;text-transform:uppercase;letter-spacing:.5px}} .knowledge-card details{{margin-top:12px;background:#f7fafc;border-radius:9px;padding:10px 12px}} .knowledge-card details summary{{cursor:pointer;color:#1769aa;font-weight:700;font-size:13px}} .knowledge-card details ul{{margin:10px 0 2px;padding-left:20px;color:#465d70;font-size:13px;line-height:1.55}} .knowledge-card footer{{margin-top:13px;font-size:12px;color:var(--muted)}} .index-count{{white-space:nowrap;background:#edf5fa;color:#3f657e;border-radius:999px;padding:4px 8px;font-size:11px;font-weight:700}}
.form-section{{grid-column:1/-1;border-top:1px solid #e4edf4;padding-top:18px;margin-top:4px}} .form-section h2{{font-size:17px;margin:0 0 5px}} .form-section p{{margin:0;color:var(--muted);font-size:13px}}
 .code-toolbar{{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin:18px 0 10px}} .code-toolbar strong{{font:600 13px Consolas,monospace;color:#38546c}} .code-toolbar span{{color:var(--muted);font-size:13px}} .code-frame{{margin-top:0;background:#071522;border:1px solid #1f4a68;border-radius:13px;overflow:hidden;box-shadow:0 12px 28px #0a25421c}} .code-header{{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:8px 15px;background:linear-gradient(90deg,#0d263c,#0b1d30);border-bottom:1px solid #1d425b;color:#8eafc3;font:12px Consolas,"Cascadia Code",monospace}} .code-header .language{{color:#68d5df;text-transform:uppercase;letter-spacing:.8px;font-size:10px;font-weight:700}} .code-frame pre{{margin:0;border:0;padding:5px 0;background:transparent;overflow:auto}} .source-code{{counter-reset:source-line;display:block;min-width:max-content;white-space:pre;line-height:1.15;font-size:13px;tab-size:4;color:#dcebf7}} .source-line{{display:block;min-height:1.15em;padding-right:28px}} .source-line:hover{{background:#ffffff08}} .source-line:before{{counter-increment:source-line;content:counter(source-line);display:inline-block;width:58px;margin-right:17px;text-align:right;color:#52708b;border-right:1px solid #20415b;padding-right:14px;user-select:none}} .tok-comment{{color:#70909a;font-style:italic}} .tok-string{{color:#a8d889}} .tok-keyword{{color:#70c7ff;font-weight:650}} .tok-directive{{color:#f3b66d;font-weight:650}} .tok-number{{color:#d8a6ff}} .tok-identifier{{color:#dcebf7}} .sr-only{{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}}
.mapping-card{{padding:18px 20px}} .mapping-head{{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;flex-wrap:wrap}} .mapping-asset{{font-weight:700;font-size:16px}} .mapping-flow{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;color:#39556e}} .mapping-flow code{{font-size:13px;background:#eef5fa;padding:6px 9px;border-radius:6px}} .mapping-meta{{display:flex;gap:18px;flex-wrap:wrap;color:var(--muted);font-size:13px;margin:16px 0 0}} .mapping-meta strong{{color:#415b72}} .mapping-detail{{margin-top:17px;border-top:1px solid #e3edf4;padding-top:13px}} .mapping-detail summary{{cursor:pointer;color:#1769aa;font-weight:650}} .mapping-detail table{{margin-top:13px;box-shadow:none}} .mapping-detail pre{{font-size:12px;margin-bottom:0}}
.transaction-flow{{display:grid;grid-template-columns:minmax(150px,1fr) 46px minmax(150px,1fr) 46px minmax(150px,1fr);gap:8px;align-items:center;margin:18px 0}} .flow-node{{border:1px solid #c9dce9;border-radius:11px;background:#f8fbfd;padding:13px 14px;min-height:72px}} .flow-node.bridge{{background:#edf8fb;border-color:#a9dce4}} .flow-node small{{display:block;color:#6a7e91;text-transform:uppercase;letter-spacing:.6px;font-size:10px;margin-bottom:6px}} .flow-node code{{font-size:12px;word-break:break-word}} .flow-arrow{{text-align:center;color:#1faabd;font-size:22px}} .mapping-badges{{display:flex;gap:7px;flex-wrap:wrap}} .mapping-badge{{background:#eef3f7;color:#4a6175;border-radius:7px;padding:5px 8px;font-size:11px}} .mapping-badge strong{{color:#183f5d}}
.gap-list{{display:grid;gap:10px}} .gap-row{{display:grid;grid-template-columns:minmax(200px,1fr) 2fr auto;gap:14px;align-items:center;background:#fff;border:1px solid var(--line);border-radius:11px;padding:13px 15px}} .gap-row p{{margin:0;color:var(--muted);font-size:13px}} .gap-tags{{display:flex;gap:5px;flex-wrap:wrap}}
.nav-more{{position:relative}} .nav-more>summary{{list-style:none;color:#c9e7f5;padding:8px 11px;border-radius:8px;font-size:13px;cursor:pointer}} .nav-more>summary::-webkit-details-marker{{display:none}} .nav-more>summary:after{{content:" ▾";font-size:10px}} .nav-more[open]>summary,.nav-more>summary:hover,.nav-more>summary.active{{background:#ffffff18;color:#fff}} .nav-menu{{position:absolute;right:0;top:42px;min-width:180px;background:#0c263d;border:1px solid #346078;border-radius:10px;padding:7px;box-shadow:0 14px 32px #03111f66;display:grid;z-index:10}} .nav-menu a{{display:block}}
.advanced{{margin-top:18px}} .advanced summary{{cursor:pointer;font-size:18px;font-weight:700;color:var(--ink);outline:none}} .advanced summary::marker{{color:var(--cyan)}} .advanced[open] summary{{margin-bottom:16px}}
.danger{{color:#b42318;font-weight:650}} .ok{{color:#067647;font-weight:650}} .status-badge{{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:5px 10px;background:#edf2f7;color:#526173;font-size:12px;font-weight:750;border:1px solid transparent}} .status-badge:before{{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}} .status-badge.ok{{background:#e5f7ef;color:#067647;border-color:#bee8d5}} .status-badge.warn{{background:#fff3d9;color:#9a5b00;border-color:#f1ddb3}} .status-badge.info{{background:#e8f2ff;color:#175ea8;border-color:#c7dcf5}} .status-badge.danger{{background:#fff0ee;color:#b42318;border-color:#f4c7c1}} .status-badge.muted{{background:#eef2f6;color:#667587;border-color:#d9e0e7}}
.asset-header{{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:18px}} .asset-kicker{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}} .asset-subline{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;color:var(--muted);font-size:13px}} .asset-actions{{display:flex;gap:9px;align-items:center;flex-wrap:wrap}} .asset-actions form{{margin:0}} .secondary-button{{display:inline-flex;align-items:center;padding:9px 12px;border:1px solid #b9cede;border-radius:8px;background:#fff;color:#155f99;text-decoration:none;font-weight:700;font-size:13px}} .secondary-button:hover{{background:#eff7fd;border-color:#8fb9d8}}
.readiness-banner{{display:grid;grid-template-columns:auto 1fr;gap:14px;align-items:flex-start;border-radius:14px;padding:17px 19px;margin:18px 0;border:1px solid}} .readiness-banner strong{{display:block;margin-bottom:4px}} .readiness-banner p{{margin:0;color:#42566a}} .readiness-banner.ok{{background:#effaf5;border-color:#bfe5d5}} .readiness-banner.info{{background:#eef6ff;border-color:#c6dcf5}} .readiness-banner.warn{{background:#fff8e8;border-color:#efd9a7}} .readiness-banner.danger{{background:#fff1ef;border-color:#f0c5bf}} .readiness-banner.muted{{background:#f3f5f7;border-color:#dce2e8}}
.asset-tabs{{display:flex;gap:6px;border-bottom:1px solid var(--line);margin-top:24px;overflow-x:auto}} .asset-tab{{border:0;border-bottom:3px solid transparent;border-radius:8px 8px 0 0;background:transparent;color:#53677b;box-shadow:none;padding:11px 15px;white-space:nowrap}} .asset-tab:hover{{filter:none;background:#e9f3fa;color:#174f7d}} .asset-tab[aria-selected="true"]{{color:#0d5b91;background:#fff;border-bottom-color:var(--cyan)}} .tab-panel{{padding-top:18px}} .tab-panel[hidden]{{display:none}}
.doc-layout{{display:grid;grid-template-columns:minmax(0,1fr) 230px;gap:22px;align-items:start}} .markdown-body{{background:#fff;border:1px solid var(--line);border-radius:15px;padding:28px 32px;box-shadow:0 8px 24px #173b5d0c;min-width:0}} .markdown-body>h1:first-child{{margin-top:0}} .markdown-body h1{{font-size:29px;border-bottom:1px solid #e5edf4;padding-bottom:12px;margin:0 0 22px}} .markdown-body h2{{font-size:21px;margin:30px 0 12px;padding-top:3px}} .markdown-body h3{{font-size:17px;margin:24px 0 9px}} .markdown-body p,.markdown-body li{{font-size:15px;line-height:1.75;color:#34495e}} .markdown-body p{{margin:10px 0}} .markdown-body ul,.markdown-body ol{{padding-left:24px}} .markdown-body li+li{{margin-top:5px}} .markdown-body code{{background:#edf5fa;border:1px solid #d9e8f1;border-radius:5px;padding:2px 5px;font-size:.92em}} .markdown-body pre code{{background:transparent;border:0;padding:0;color:#d9eaf5}} .markdown-body blockquote{{margin:15px 0;padding:10px 15px;border-left:4px solid var(--cyan);background:#eef8fb;color:#375a6d}} .md-table-wrap{{overflow-x:auto;margin:16px 0}} .markdown-body table{{box-shadow:none}} .doc-toc{{position:sticky;top:98px;background:#f8fbfd;border:1px solid var(--line);border-radius:13px;padding:17px}} .doc-toc strong{{display:block;margin-bottom:10px;font-size:13px;text-transform:uppercase;letter-spacing:.7px;color:#4e657a}} .doc-toc a{{display:block;padding:5px 0;color:#49677f;text-decoration:none;font-size:13px;line-height:1.35}} .doc-toc a.sub{{padding-left:12px}} .doc-toc a:hover{{color:#0d6ea6}}
.knowledge-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}} .empty-note{{padding:13px 15px;border:1px dashed #bed0df;border-radius:10px;background:#f8fbfd;color:var(--muted)}} .file-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}} .file-card{{display:flex;justify-content:space-between;gap:14px;align-items:center;padding:15px 16px;border:1px solid var(--line);background:#fff;border-radius:11px;text-decoration:none}} .file-card:hover{{border-color:#91c8dc;background:#f5fbfe}} .file-card code{{word-break:break-all}} .file-type{{font-size:11px;text-transform:uppercase;color:#60758a;background:#edf3f7;border-radius:6px;padding:4px 7px}}
 .document-toolbar{{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:14px}} .document-toolbar .actions{{display:flex;gap:8px;align-items:center}} .copy-button{{padding:7px 10px;font-size:12px;box-shadow:none}} .sr-only{{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}}
.template-hero:after{{content:"RTL / REVIEW"}} .template-intro{{max-width:780px}} .template-workflow{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:20px 0 28px}} .template-step{{position:relative;padding:20px 20px 18px 58px;min-height:142px}} .template-step-number{{position:absolute;left:18px;top:19px;width:27px;height:27px;border-radius:8px;display:grid;place-items:center;background:#e4f5f8;color:#087586;font:800 12px Consolas,monospace;border:1px solid #b8e4e8}} .template-step h3{{margin:0 0 7px;font-size:17px}} .template-step p{{margin:0;color:var(--muted);font-size:13px;line-height:1.65}} .template-overview td:first-child{{font-weight:750;white-space:nowrap;color:#174f72}} .template-overview td:nth-child(2){{color:#40576b;line-height:1.55}} .template-actions{{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;margin:12px 0}} .template-actions p{{margin:0}} .template-copy-panel{{margin-top:20px;padding:0;overflow:hidden}} .template-copy-panel summary{{cursor:pointer;padding:17px 20px;font-weight:750;color:#174f72;background:#f5f9fc}} .template-copy-panel[open] summary{{border-bottom:1px solid var(--line)}} .template-copy-panel pre{{margin:0;border:0;border-radius:0;max-height:520px;white-space:pre;line-height:1.4}}
.readme-editor{{display:grid;gap:12px;margin:20px 0}} .readme-editor textarea{{min-height:560px;font:14px/1.6 Consolas,"Cascadia Code",monospace;color:#dbeaf4;background:#0b172a;border-color:#244c69;padding:18px;tab-size:4}} .suggestion-box{{grid-column:1/-1;background:#f7fafc;border:1px dashed #c7d8e4;border-radius:9px;padding:11px 12px}} .suggestion-box strong{{display:block;font-size:12px;color:#5a7084;margin-bottom:7px}} .suggestion-chip{{background:#e6f2fb;color:#17648a;border:1px solid #c7e5f0;border-radius:999px;padding:5px 9px;margin:2px;font-size:11px;font-weight:650;box-shadow:none}} .suggestion-chip:hover{{filter:none;background:#d5edf8}}
header nav a.active{{background:#ffffff18;color:#fff;box-shadow:inset 0 0 0 1px #72d9e450}}
@media(max-width:1050px){{.filter-panel form{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media(max-width:900px){{.doc-layout{{grid-template-columns:1fr}}.doc-toc{{position:static;order:-1}}.knowledge-grid{{grid-template-columns:1fr}}.asset-header{{flex-direction:column}}.transaction-flow{{grid-template-columns:1fr}}.flow-arrow{{transform:rotate(90deg)}}.template-workflow{{grid-template-columns:1fr}}}}
 @media(max-width:700px){{header{{padding:14px 16px;align-items:flex-start;gap:10px;flex-direction:column}}main{{margin:22px auto;padding:0 14px}}h1{{font-size:25px}}.hero{{padding:24px}}.hero h1{{font-size:29px}}.hero-actions{{align-items:flex-start;flex-direction:column;gap:13px}}table{{font-size:13px;display:block;overflow-x:auto;white-space:nowrap}}input{{min-width:160px}}.markdown-body{{padding:21px 18px}}.source-line:before{{width:42px;margin-right:11px;padding-right:9px}}.source-line{{padding-right:20px}}.code-frame pre{{padding:4px 0}}.code-header{{padding:7px 12px}}.filter-panel form{{grid-template-columns:1fr}}.asset-card-list{{grid-template-columns:1fr}}.gap-row{{grid-template-columns:1fr}}.nav-more{{position:static}}.nav-menu{{position:static;box-shadow:none;margin-top:5px}}}}
@media(prefers-reduced-motion:reduce){{*,*:before,*:after{{scroll-behavior:auto!important;transition:none!important;animation:none!important}}}}
</style></head><body><a class="skip-link" href="#main-content">跳到主要内容</a><header><div class="brand"><span class="brand-mark" aria-hidden="true"></span><a class="nav" href="/"><span class="brand-copy"><span>System IP Design Hub</span><small>RTL / DMA / AXI / PCIe / CXL</small></span></a></div><nav aria-label="主导航"><a href="/assets">资产</a><a href="/patterns">设计模式</a><a href="/problems">问题索引</a><a href="/mappings">Bridge Mapping</a><details class="nav-more"><summary>工具</summary><div class="nav-menu"><a href="/templates/rtl-module-design-review">RTL 设计模板</a><a href="/import">导入 RTL</a><a href="/protocols">协议索引</a><a href="/dependencies">依赖关系</a><a href="/report">待完善项</a></div></details></nav></header><main id="main-content">{body}</main><script>
document.querySelectorAll('.asset-tab').forEach((button)=>button.addEventListener('click',()=>{{
  const group=button.closest('[data-tabs]');
  group.querySelectorAll('.asset-tab').forEach((item)=>item.setAttribute('aria-selected',String(item===button)));
  group.querySelectorAll('.tab-panel').forEach((panel)=>panel.hidden=panel.id!==button.dataset.tab);
}}));
document.querySelectorAll('[data-copy-target]').forEach((button)=>button.addEventListener('click',async()=>{{
  const target=document.querySelector(button.dataset.copyTarget);
  if(!target)return;
  try{{await navigator.clipboard.writeText(target.textContent||'');button.textContent='已复制';setTimeout(()=>button.textContent='复制',1400)}}catch(error){{button.textContent='复制失败'}}
}}));
document.querySelectorAll('[data-add-target]').forEach((button)=>button.addEventListener('click',()=>{{
  const target=document.querySelector(button.dataset.addTarget);if(!target)return;
  const values=target.value.split(/\\r?\\n/).map((item)=>item.trim()).filter(Boolean);
  if(!values.includes(button.dataset.value))values.push(button.dataset.value);
  target.value=values.join('\\n');target.focus();
}}));
document.querySelectorAll('[role="tablist"]').forEach((list)=>list.addEventListener('keydown',(event)=>{{
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  const tabs=[...list.querySelectorAll('[role="tab"]')];const current=tabs.indexOf(document.activeElement);if(current<0)return;
  event.preventDefault();let next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(current+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;tabs[next].focus();tabs[next].click();
}}));
const path=window.location.pathname;
document.querySelectorAll('header nav a').forEach((link)=>{{const href=link.getAttribute('href');if(href!=='/'&&path.startsWith(href)){{link.classList.add('active');const menu=link.closest('.nav-more');if(menu)menu.querySelector('summary').classList.add('active')}}}});
</script></body></html>"""
    return content.encode("utf-8")


def pills(values: list[object]) -> str:
    return " ".join(f'<span class="pill">{esc(v)}</span>' for v in values) or '<span class="muted">—</span>'


def status_badge(status: object) -> str:
    label, hint, style = status_info(status)
    return f'<span class="status-badge {style}" title="{esc(hint)}">{esc(label)}</span>'


class Handler(BaseHTTPRequestHandler):
    server_version = "SystemIPHub/0.1"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def send_bytes(self, body: bytes, content_type: str = "text/html; charset=utf-8", status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, data: object, status: int = 200) -> None:
        self.send_bytes(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"), "application/json; charset=utf-8", status)

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
            if path == "/api/health":
                self.send_json({"status": "ok", "asset_root": str(ASSET_ROOT), "database": str(DB_PATH), "summary": catalog.summary()})
            elif path == "/api/protocols":
                self.send_json(catalog.protocols())
            elif path == "/api/mappings":
                self.send_json(catalog.mappings(query.get("q", "")))
            elif path == "/api/verification":
                self.send_json(catalog.verification_summary())
            elif path == "/api/dependencies":
                self.send_json(catalog.dependency_graph())
            elif path == "/api/report":
                self.send_json(catalog.health_report())
            elif path == "/api/patterns":
                self.send_json(self.index_data("design_patterns", query.get("q", "")))
            elif path == "/api/problems":
                self.send_json(self.index_data("problem_index", query.get("q", "")))
            elif path == "/api/assets":
                self.send_json(catalog.list_assets(query.get("q", ""), query.get("category", ""), query.get("tag", ""), query.get("protocol", ""), query.get("status", "")))
            elif path.startswith("/api/assets/"):
                name = path[len("/api/assets/"):]
                asset = catalog.get_asset(name)
                self.send_json(asset or {"error": "asset not found"}, HTTPStatus.OK if asset else HTTPStatus.NOT_FOUND)
            elif path == "/":
                self.dashboard()
            elif path == "/assets":
                self.assets_page(query)
            elif path == "/protocols":
                self.protocols_page()
            elif path == "/mappings":
                self.mappings_page(query)
            elif path == "/verification":
                self.verification_page()
            elif path == "/dependencies":
                self.dependencies_page()
            elif path == "/report":
                self.report_page()
            elif path == "/patterns":
                self.patterns_page(query)
            elif path == "/problems":
                self.problems_page(query)
            elif path == "/templates/rtl-module-design-review":
                self.rtl_template_page()
            elif path == "/examples/axi-channel-slice":
                self.axi_slice_example_page()
            elif path == "/import":
                self.import_page()
            elif path.startswith("/assets/") and path.endswith("/readme/edit"):
                self.edit_readme_page(path[len("/assets/"):-len("/readme/edit")].rstrip("/"))
            elif path.startswith("/assets/") and path.endswith("/edit"):
                self.edit_asset_page(path[len("/assets/"):-len("/edit")].rstrip("/"))
            elif path.startswith("/assets/") and "/file/" in path:
                asset_name, relative_file = path[len("/assets/"):].split("/file/", 1)
                self.file_page(asset_name, relative_file)
            elif path.startswith("/assets/"):
                self.asset_page(path[len("/assets/"):])
            else:
                self.send_bytes(page("Not Found", "<h1>404</h1><p>页面不存在。</p>"), status=HTTPStatus.NOT_FOUND)
        except Exception:
            traceback.print_exc()
            self.send_bytes(page("Server Error", "<h1>500</h1><p>服务器内部错误，请查看终端日志。</p>"), status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/catalog/scan":
            self.send_json(catalog.scan())
        elif parsed.path.startswith("/api/assets/") and parsed.path.endswith("/delete"):
            name = unquote(parsed.path[len("/api/assets/"):-len("/delete")].rstrip("/"))
            self.delete_imported_asset(name, as_json=True)
        elif parsed.path.startswith("/assets/") and parsed.path.endswith("/readme/edit"):
            name = unquote(parsed.path[len("/assets/"):-len("/readme/edit")].rstrip("/"))
            self.save_readme(name)
        elif parsed.path.startswith("/assets/") and parsed.path.endswith("/edit"):
            name = unquote(parsed.path[len("/assets/"):-len("/edit")].rstrip("/"))
            self.save_asset_edit(name)
        elif parsed.path.startswith("/assets/") and parsed.path.endswith("/delete"):
            name = unquote(parsed.path[len("/assets/"):-len("/delete")].rstrip("/"))
            self.delete_imported_asset(name)
        elif parsed.path in {"/api/import/scan", "/api/import/create", "/import"}:
            payload = self.read_payload()
            try:
                project_path = payload.get("project_path", "")
                category = payload.get("category", "imported_rtl") or "imported_rtl"
                result = scan_project(Path(project_path))
                if parsed.path == "/api/import/scan" or payload.get("action") == "scan":
                    result["drafts"] = [make_draft(module, result["project_root"], category) for module in result["modules"]]
                    if parsed.path == "/import":
                        self.import_page(result)
                    else:
                        self.send_json(result)
                else:
                    created = self.create_imported_assets(result, category)
                    catalog.scan()
                    result["created"] = created
                    if parsed.path == "/import":
                        self.import_page(result)
                    else:
                        self.send_json(result)
            except Exception as exc:
                if parsed.path == "/import":
                    self.import_page({"error": str(exc)})
                else:
                    self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        else:
            self.send_json({"error": "endpoint not found"}, HTTPStatus.NOT_FOUND)

    def _save_asset_metadata(self, name: str, payload: dict[str, str]) -> dict[str, object]:
        asset = catalog.get_asset(name)
        if not asset:
            raise ValueError("asset not found")
        metadata_path = Path(asset["metadata_path"]).resolve()
        asset_root = ASSET_ROOT.resolve()
        if asset_root not in metadata_path.parents or metadata_path.suffix.lower() not in {".yaml", ".yml", ".json"}:
            raise ValueError("metadata path is outside the asset root")
        metadata = dict(asset.get("metadata") or {})
        metadata["display_name"] = payload.get("display_name", "").strip() or name
        metadata["description"] = payload.get("description", "").strip()
        metadata["version"] = payload.get("version", "draft").strip() or "draft"
        metadata["category"] = payload.get("category", "uncategorized").strip() or "uncategorized"
        metadata["status"] = payload.get("status", "draft").strip() or "draft"
        metadata["tags"] = [x.strip() for x in payload.get("tags", "").split(",") if x.strip()]
        metadata["features"] = [x.strip() for x in payload.get("features", "").splitlines() if x.strip()]
        metadata["design_patterns"] = [x.strip() for x in payload.get("design_patterns", "").splitlines() if x.strip()]
        metadata["problem_index"] = [x.strip() for x in payload.get("problem_index", "").splitlines() if x.strip()]
        metadata["limitations"] = [x.strip() for x in payload.get("limitations", "").splitlines() if x.strip()]
        if "verification_checks" in payload:
            verification = dict(metadata.get("verification") or {})
            verification_checks = payload.get("verification_checks", "").split(",")
            for check_type in (item.strip() for item in verification_checks):
                if check_type:
                    status = payload.get(f"verification_{check_type}", "not_run").strip() or "not_run"
                    command = payload.get(f"verification_command_{check_type}", "").strip()
                    report_path = payload.get(f"verification_report_{check_type}", "").strip()
                    verification[check_type] = {"status": status, "command": command, "report_path": report_path} if command or report_path else status
            if payload.get("verification_last_checked", "").strip():
                verification["last_checked"] = payload["verification_last_checked"].strip()
            else:
                verification.pop("last_checked", None)
            if payload.get("verification_notes", "").strip():
                verification["notes"] = payload["verification_notes"].strip()
            else:
                verification.pop("notes", None)
            metadata["verification"] = verification
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        catalog.scan()
        refreshed = catalog.get_asset(name)
        if not refreshed:
            raise ValueError("asset disappeared after save")
        return refreshed

    def save_asset_edit(self, name: str) -> None:
        try:
            asset = self._save_asset_metadata(name, self.read_payload())
            self.edit_asset_page(name, message="已保存资产元数据。", asset=asset)
        except Exception as exc:
            self.edit_asset_page(name, message=f"保存失败：{exc}", error=True)

    def _readme_target(self, asset: dict[str, object]) -> tuple[Path, Path]:
        root = Path(str(asset["root_path"])).resolve()
        asset_root = ASSET_ROOT.resolve()
        if root != asset_root and asset_root not in root.parents:
            raise ValueError("asset root is outside the configured library")
        _content, existing = read_asset_readme(root)
        target = (existing or (root / "README.md")).resolve()
        if root not in target.parents:
            raise ValueError("README path is outside the asset root")
        return root, target

    def save_readme(self, name: str) -> None:
        try:
            asset = catalog.get_asset(name)
            if not asset:
                raise ValueError("asset not found")
            _root, target = self._readme_target(asset)
            content = self.read_payload().get("content", "").replace("\r\n", "\n")
            target.write_text(content.rstrip() + "\n", encoding="utf-8")
            self.edit_readme_page(name, message="README 已保存，资产详情页会立即使用新内容。")
        except Exception as exc:
            self.edit_readme_page(name, message=f"保存失败：{exc}", error=True)

    def edit_readme_page(self, name: str, message: str = "", error: bool = False) -> None:
        asset = catalog.get_asset(name)
        if not asset:
            self.send_bytes(page("Not Found", "<h1>资产不存在</h1><p><a href='/assets'>返回资产库</a></p>"), status=HTTPStatus.NOT_FOUND)
            return
        try:
            _root, target = self._readme_target(asset)
            content = target.read_text(encoding="utf-8") if target.is_file() else f"# {asset['display_name']}\n\n"
        except Exception as exc:
            self.send_bytes(page("README Error", f"<h1>无法读取 README</h1><p>{esc(exc)}</p>"), status=HTTPStatus.BAD_REQUEST)
            return
        preview, _toc = render_markdown(content)
        notice = f"<div class='readiness-banner {'danger' if error else 'ok'}'><div><strong>{esc(message)}</strong></div></div>" if message else ""
        body = f"""<p><a href='/assets/{quote(name)}'>← {esc(asset['display_name'])}</a></p><div class='eyebrow'>DOCUMENT / EDIT</div><h1>编辑 README</h1><p class='muted'>保存后无需重新扫描目录，刷新资产详情页即可看到新内容。</p>{notice}<form class='readme-editor' method='post' action='/assets/{quote(name)}/readme/edit'><label for='readme-content'><strong>Markdown 内容</strong></label><textarea id='readme-content' name='content' spellcheck='false'>{esc(content)}</textarea><div><button type='submit'>保存 README</button> <a class='secondary-button' href='/assets/{quote(name)}'>取消</a></div></form><div class='section-title'><h2>当前内容预览</h2></div><article class='markdown-body'>{preview}</article>"""
        self.send_bytes(page(f"Edit README - {asset['display_name']}", body))

    def delete_imported_asset(self, name: str, as_json: bool = False) -> None:
        try:
            asset = catalog.get_asset(name)
            if not asset:
                raise ValueError("asset not found")
            asset_root = Path(asset["root_path"]).resolve()
            imported_root = (ASSET_ROOT / "imported").resolve()
            if imported_root not in asset_root.parents or asset_root == imported_root:
                raise PermissionError("only imported assets can be deleted from the web UI")
            if not asset_root.is_dir():
                raise FileNotFoundError("asset directory not found")
            shutil.rmtree(asset_root)
            catalog.delete_asset_record(name)
            if as_json:
                self.send_json({"deleted": name})
            else:
                self.send_bytes(page("Asset Deleted", f"<div class='card ok'><h1>资产已删除</h1><p><code>{esc(name)}</code> 已从导入资产目录和索引中移除。</p><p><a href='/assets'>返回资产库</a></p></div>"))
        except Exception as exc:
            if as_json:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            else:
                self.send_bytes(page("Delete Failed", f"<div class='card danger'><h1>删除失败</h1><p>{esc(exc)}</p><p><a href='/assets/{quote(name)}'>返回资产详情</a></p></div>"), status=HTTPStatus.BAD_REQUEST)

    def read_payload(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        content_type = self.headers.get("Content-Type", "")
        if "application/json" in content_type:
            value = json.loads(raw or "{}")
            return value if isinstance(value, dict) else {}
        return {key: values[0] for key, values in parse_qs(raw).items()}

    def edit_asset_page(self, name: str, message: str = "", error: bool = False, asset: dict[str, object] | None = None) -> None:
        asset = asset or catalog.get_asset(name)
        if not asset:
            self.send_bytes(page("Not Found", "<h1>资产不存在</h1><p><a href='/assets'>返回资产库</a></p>"), status=HTTPStatus.NOT_FOUND)
            return
        metadata = asset.get("metadata") or {}
        tags = ", ".join(str(x) for x in (metadata.get("tags") or asset.get("tags") or []))
        features = "\n".join(str(x) for x in (metadata.get("features") or []))
        design_patterns = "\n".join(str(x) for x in (metadata.get("design_patterns") or []))
        problem_index = "\n".join(str(x) for x in (metadata.get("problem_index") or []))
        limitations = "\n".join(str(x) for x in (metadata.get("limitations") or []))
        selected_status = str(metadata.get("status", asset["status"]) or "draft")
        if selected_status in {"stable", "simulation_checked"}:
            selected_status = "ready"
        pattern_names = sorted({str(entry["name"]) for entry in self.index_data("design_patterns")}, key=str.lower)
        problem_names = sorted({str(entry["name"]) for entry in self.index_data("problem_index")}, key=str.lower)
        pattern_suggestions = "".join(f"<button class='suggestion-chip' type='button' data-add-target='#design-patterns' data-value='{esc(value)}'>{esc(value)}</button>" for value in pattern_names)
        problem_suggestions = "".join(f"<button class='suggestion-chip' type='button' data-add-target='#problem-index' data-value='{esc(value)}'>{esc(value)}</button>" for value in problem_names)
        notice = f"<div class='card {'danger' if error else 'ok'}'>{esc(message)}</div>" if message else ""
        body = f"""<p><a href='/assets/{quote(name)}'>← {esc(asset['display_name'])}</a></p>
<div class='eyebrow'>ASSET METADATA / EDIT</div><h1>编辑资产信息</h1><p class='muted'>只修改 metadata.yaml 中的描述性字段；RTL 源码、接口提取结果、mapping 和依赖关系保持不变。</p>{notice}
<div class='card'><form method='post' action='/assets/{quote(name)}/edit' style='display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:start'><div class='form-section'><h2>基本信息</h2><p>资产身份、分类和简要描述。</p></div>
<label>显示名称<br><input name='display_name' value='{esc(metadata.get('display_name', asset['display_name']))}' required></label>
<label>版本<br><input name='version' value='{esc(metadata.get('version', asset['version']))}'></label>
<label>分类<br><input name='category' value='{esc(metadata.get('category', asset['category']))}' required></label>
<label>复用状态<br><select name='status'>{''.join(f"<option value='{value}' {'selected' if value == selected_status else ''}>{label} · {hint}</option>" for value, (label, hint, _style) in STATUS_META.items() if value not in {'stable','simulation_checked'})}</select></label>
<label style='grid-column:1/-1'>描述<br><textarea name='description'>{esc(metadata.get('description', asset['description']))}</textarea></label>
<label style='grid-column:1/-1'>标签（逗号分隔）<br><input style='width:100%' name='tags' value='{esc(tags)}'></label>
<div class='form-section'><h2>设计知识</h2><p>把组件背后的设计模式和问题经验记录下来，供索引页反查。</p></div>
<label style='grid-column:1/-1'>Features（每行一项）<br><textarea name='features'>{esc(features)}</textarea></label>
<label style='grid-column:1/-1'>设计模式（每行一项）<br><textarea id='design-patterns' name='design_patterns'>{esc(design_patterns)}</textarea></label><div class='suggestion-box'><strong>点击添加已有设计模式</strong>{pattern_suggestions or '<span class="muted">暂无已有模式</span>'}</div>
<label style='grid-column:1/-1'>问题索引（每行一项）<br><textarea id='problem-index' name='problem_index'>{esc(problem_index)}</textarea></label><div class='suggestion-box'><strong>点击添加已有问题索引</strong>{problem_suggestions or '<span class="muted">暂无已有问题</span>'}</div>
<div class='form-section'><h2>使用说明</h2><p>记录复用前需要确认的边界条件和限制。</p></div>
<label style='grid-column:1/-1'>使用限制（每行一条）<br><textarea name='limitations'>{esc(limitations)}</textarea></label>
<div style='grid-column:1/-1'><button type='submit'>保存元数据</button> <a href='/assets/{quote(name)}'>取消</a></div></form></div>"""
        self.send_bytes(page(f"Edit {asset['display_name']}", body))

    def create_imported_assets(self, result: dict[str, object], category: str) -> list[str]:
        project_root = Path(str(result["project_root"])).resolve()
        target_root = (ASSET_ROOT / "imported").resolve()
        target_root.mkdir(parents=True, exist_ok=True)
        created: list[str] = []
        for module in result.get("modules", []):
            draft = make_draft(module, str(project_root), category)
            base_name = str(draft["name"])
            target_dir = target_root / base_name
            suffix = 2
            while target_dir.exists():
                target_dir = target_root / f"{base_name}_{suffix}"
                suffix += 1
            target_dir.mkdir(parents=True)
            source_file = (project_root / str(module["source_file"])).resolve()
            if project_root not in source_file.parents or not source_file.is_file():
                shutil.rmtree(target_dir, ignore_errors=True)
                continue
            rtl_dir = target_dir / "rtl"
            rtl_dir.mkdir()
            shutil.copy2(source_file, rtl_dir / source_file.name)
            draft["name"] = target_dir.name
            draft["files"] = {"rtl": [f"rtl/{source_file.name}"]}
            (target_dir / "metadata.yaml").write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
            (target_dir / "README.md").write_text(
                f"# {draft['display_name']}\n\nGenerated by System IP Design Hub importer from `{module['source_file']}`.\n\nReview this draft before reuse.\n",
                encoding="utf-8",
            )
            created.append(target_dir.name)
        return created

    def dashboard(self) -> None:
        all_assets = catalog.list_assets()
        assets = [asset for asset in all_assets if not is_sample_asset(asset)]
        needs_fix = [asset for asset in assets if str(asset["status"]) == "needs_fix"]
        constrained = [asset for asset in assets if str(asset["status"]) == "constrained"]
        patterns = self.index_data("design_patterns")
        problems = self.index_data("problem_index")
        category_counts: dict[str, int] = {}
        for asset in assets:
            category = str(asset["category"])
            category_counts[category] = category_counts.get(category, 0) + 1
        categories = " ".join(f"<a class='pill' href='/assets?category={quote(category)}'>{esc(category)} · {count}</a>" for category, count in sorted(category_counts.items(), key=lambda item: (-item[1], item[0])))
        priority_rows = "".join(f"<div class='gap-row'><div><a href='/assets/{quote(asset['name'])}'><strong>{esc(asset['display_name'])}</strong></a><br><code>{esc(asset['name'])}</code></div><p>{esc(current_conclusion(read_asset_readme(Path(str(asset['root_path'])))[0]) or asset['description'])}</p>{status_badge(asset['status'])}</div>" for asset in needs_fix[:6])
        body = f"""<section class='hero'><div class='eyebrow'>SYSTEM IP / DESIGN WORKSPACE</div><h1>System IP Design Hub</h1><p>面向 RTL、DMA、AXI、PCIe 与 CXL 的本地设计资产、模式和问题知识库。</p><div class='hero-actions'><a class='hero-button' href='/assets'>进入资产库</a><a class='hero-link' href='/report'>查看待完善项 →</a></div></section>
<div class='section-title'><h2>资产概览</h2></div><div class='stat-grid'><div class='card stat-card'><div class='eyebrow'>DESIGN ASSETS</div><div class='stat-value'>{len(assets)}</div><div class='stat-label'>默认不含 {sum(1 for asset in all_assets if is_sample_asset(asset))} 个 Sample</div></div><div class='card stat-card'><div class='eyebrow'>NEEDS FIX</div><div class='stat-value'>{len(needs_fix)}</div><div class='stat-label'>修复后再复用</div></div><div class='card stat-card'><div class='eyebrow'>CONSTRAINED</div><div class='stat-value'>{len(constrained)}</div><div class='stat-label'>满足约束后复用</div></div><div class='card stat-card'><div class='eyebrow'>KNOWLEDGE INDEX</div><div class='stat-value'>{len(patterns)} / {len(problems)}</div><div class='stat-label'>设计模式 / 问题索引</div></div></div><div class='card'><strong>分类</strong><p>{categories}</p></div>
<div class='grid dashboard-links' style='margin-top:18px'><a class='card link-card' href='/assets'><span class='eyebrow'>ASSET LIBRARY</span><h3>设计资产</h3><p>检索 README、接口、源码与复用状态。</p><span>浏览资产 →</span></a><a class='card link-card' href='/patterns'><span class='eyebrow'>PATTERN LIBRARY</span><h3>设计模式</h3><p>按可复用结构和实现方法反查组件。</p><span>进入索引 →</span></a><a class='card link-card' href='/problems'><span class='eyebrow'>ENGINEERING PROBLEMS</span><h3>问题索引</h3><p>从 corner case、症状和根因反查经验。</p><span>进入索引 →</span></a><a class='card link-card' href='/mappings'><span class='eyebrow'>PROTOCOL MAPPING</span><h3>Bridge Mapping</h3><p>查看 PCIe/CXL 到 AXI 的事务转换规则。</p><span>查看 Mapping →</span></a><a class='card link-card' href='/templates/rtl-module-design-review'><span class='eyebrow'>DESIGN DOCUMENT</span><h3>RTL 设计模板</h3><p>用统一结构记录模块架构、实现、验证与复盘。</p><span>打开模板 →</span></a></div>
<div class='section-title'><h2>优先修复</h2></div><div class='gap-list'>{priority_rows or '<div class="card ok">当前没有标记为 Needs Fix 的资产。</div>'}</div>"""
        self.send_bytes(page("Dashboard", body))

    def import_page(self, result: dict[str, object] | None = None) -> None:
        result = result or {}
        error = f"<div class='card danger'>{esc(result['error'])}</div>" if result.get("error") else ""
        created = result.get("created") or []
        created_html = f"<div class='card ok'><strong>已导入 {len(created)} 个资产：</strong> {pills(list(created))}</div>" if created else ""
        modules = result.get("modules") or []
        rows = "".join(
            f"<tr><td><code>{esc(m['name'])}</code></td><td>{esc(m['source_file'])}</td><td>{len(m.get('parameters', []))}</td><td>{len(m.get('ports', []))}</td><td>{'clock/reset' if m.get('has_clock') or m.get('has_reset') else 'combinational'}</td></tr>"
            for m in modules
        )
        scan_html = f"<div class='card' style='margin-top:18px'><h2>扫描结果</h2><p class='muted'>文件 {result.get('file_count', 0)} 个，module {result.get('module_count', 0)} 个。</p><table><tr><th>Module</th><th>Source</th><th>Parameters</th><th>Ports</th><th>Signals</th></tr>{rows or '<tr><td colspan=5 class=muted>暂无扫描结果</td></tr>'}</table>{'<form method="post" action="/import"><input type="hidden" name="project_path" value="'+esc(result.get('project_root',''))+'"><input type="hidden" name="category" value="imported_rtl"><input type="hidden" name="action" value="create"><button>确认导入这些资产</button></form>' if modules else ''}</div>"
        body = f"""<div class='eyebrow'>INGEST / RTL PROJECT</div><h1>导入 RTL 项目</h1><p class='muted'>扫描本地 .v/.sv/.vh/.svh 文件，提取 module、parameter 和 port，生成可编辑资产草稿。不会执行源项目命令。</p>{error}{created_html}<div class='card'><form method='post' action='/import'><input name='project_path' placeholder='项目目录绝对路径' required><input name='category' value='imported_rtl' placeholder='资产分类'><input type='hidden' name='action' value='scan'><button>扫描项目</button></form><p class='muted'>导入确认后，源码会复制到本地 assets/imported/，原项目保持不变。</p></div>{scan_html}"""
        self.send_bytes(page("Import RTL", body))

    def rtl_shape(self, asset: dict[str, object], metadata: dict[str, object], files: list[str]) -> tuple[list[dict[str, object]], list[dict[str, object]], str]:
        parameters = metadata.get("parameters") if isinstance(metadata.get("parameters"), list) else []
        interfaces = metadata.get("interfaces") or metadata.get("ports")
        interfaces = interfaces if isinstance(interfaces, list) else []
        module_name = str(metadata.get("module_name") or metadata.get("name") or asset["name"])
        if parameters and interfaces:
            return parameters, interfaces, module_name
        root = Path(str(asset["root_path"]))
        for relative in files:
            candidate = (root / relative).resolve()
            if candidate.suffix.lower() not in {".v", ".sv", ".vh", ".svh"}:
                continue
            try:
                modules = parse_rtl_file(candidate, root)
            except Exception:
                continue
            if modules:
                module = next((item for item in modules if item["name"] == module_name), modules[0])
                if not parameters:
                    parameters = module.get("parameters", [])
                if not interfaces:
                    interfaces = module.get("ports", [])
                module_name = str(module["name"])
                break
        return parameters, interfaces, module_name

    def parameter_table(self, parameters: list[dict[str, object]]) -> str:
        if not parameters:
            return "<p class='muted'>未提取到参数。可以在 metadata.yaml 中补充参数说明。</p>"
        rows = "".join(f"<tr><td><code>{esc(item.get('name'))}</code></td><td><code>{esc(item.get('default'))}</code></td><td>{esc(item.get('description') or '—')}</td></tr>" for item in parameters)
        return f"<table><tr><th>Parameter</th><th>Default</th><th>Description</th></tr>{rows}</table>"

    def interface_table(self, interfaces: list[dict[str, object]]) -> str:
        if not interfaces:
            return "<p class='muted'>未提取到端口信息。可以重新导入 RTL 或在 metadata.yaml 中补充 interfaces。</p>"
        rows = "".join(f"<tr><td><code>{esc(item.get('name'))}</code></td><td>{esc(item.get('direction') or '—')}</td><td><code>{esc(item.get('width') or item.get('range') or '1 bit')}</code></td><td>{esc(item.get('description') or '—')}</td></tr>" for item in interfaces)
        return f"<table><tr><th>Port</th><th>Direction</th><th>Width</th><th>Description</th></tr>{rows}</table>"

    def assets_page(self, query: dict[str, str]) -> None:
        all_assets = catalog.list_assets()
        categories = sorted({str(asset["category"]) for asset in all_assets if asset.get("category")})
        protocols = sorted({str(protocol["name"]) for asset in all_assets for protocol in asset.get("protocols", [])})
        statuses = sorted({str(asset["status"]) for asset in all_assets if asset.get("status")}, key=lambda item: status_info(item)[0])
        category = query.get("category", "")
        protocol = query.get("protocol", "")
        status = query.get("status", "")
        assets = catalog.list_assets("", category, query.get("tag", ""), protocol, status)
        needle = query.get("q", "").strip().lower()
        if needle:
            assets = [asset for asset in assets if needle in asset_search_text(asset)]
        scope = query.get("scope", "library")
        if scope == "samples":
            assets = [asset for asset in assets if is_sample_asset(asset)]
        elif scope != "all":
            scope = "library"
            assets = [asset for asset in assets if not is_sample_asset(asset)]
        sort = query.get("sort", "name")
        if sort == "category":
            assets.sort(key=lambda asset: (str(asset["category"]).lower(), str(asset["display_name"]).lower()))
        elif sort == "status":
            assets.sort(key=lambda asset: (status_info(asset["status"])[0], str(asset["display_name"]).lower()))
        elif sort == "updated":
            assets.sort(key=lambda asset: str(asset.get("updated_at", "")), reverse=True)
        else:
            sort = "name"
            assets.sort(key=lambda asset: str(asset["display_name"]).lower())
        view = query.get("view", "table") if query.get("view") in {"table", "cards"} else "table"

        def option(value: str, label: str, selected: str) -> str:
            return f"<option value='{esc(value)}' {'selected' if value == selected else ''}>{esc(label)}</option>"

        category_options = option("", "全部分类", category) + "".join(option(item, item, category) for item in categories)
        protocol_options = option("", "全部协议", protocol) + "".join(option(item, item, protocol) for item in protocols)
        status_options = option("", "全部复用状态", status) + "".join(option(item, f"{status_info(item)[0]} · {status_info(item)[1]}", status) for item in statuses)
        sort_options = "".join(option(value, label, sort) for value, label in (("name", "按名称"), ("category", "按分类"), ("status", "按复用状态"), ("updated", "最近更新")))

        def query_link(**updates: str) -> str:
            values = {key: value for key, value in query.items() if value}
            values.update(updates)
            return "/assets?" + urlencode(values)

        scope_links = "".join(f"<a class='{'active' if scope == value else ''}' data-scope='{value}' href='{esc(query_link(scope=value))}'>{label}</a>" for value, label in (("library", "资产库"), ("all", "全部"), ("samples", "Samples")))
        view_links = "".join(f"<a class='{'active' if view == value else ''}' data-view='{value}' href='{esc(query_link(view=value))}'>{label}</a>" for value, label in (("table", "表格"), ("cards", "卡片")))
        sample_count = sum(1 for asset in all_assets if is_sample_asset(asset))

        rows = "".join(
            f"<tr data-entry='{esc(a['name'])}'><td class='asset-table-name'><a href='/assets/{quote(a['name'])}'><strong>{esc(a['display_name'])}</strong></a> {'<span class=\"sample-mark\">sample</span>' if is_sample_asset(a) else ''}<br><code>{esc(a['name'])}</code><p>{esc(a['description']) or '—'}</p></td><td><span class='category-label'>{esc(a['category'])}</span></td><td>{pills([p['name'] for p in a['protocols']])}</td><td>{status_badge(a['status'])}</td></tr>"
            for a in assets
        )
        cards = "".join(
            f"<a class='asset-list-card' data-entry='{esc(a['name'])}' href='/assets/{quote(a['name'])}'><div><h3>{esc(a['display_name'])} {'<span class=\"sample-mark\">sample</span>' if is_sample_asset(a) else ''}</h3><code>{esc(a['name'])}</code><p>{esc(a['description']) or '—'}</p><div class='meta'><span class='category-label'>{esc(a['category'])}</span>{pills([p['name'] for p in a['protocols']])}</div></div><div>{status_badge(a['status'])}</div></a>"
            for a in assets
        )
        results = f"<div data-results='table' {'hidden' if view != 'table' or not assets else ''}><table><thead><tr><th>资产</th><th>分类</th><th>协议</th><th>复用状态</th></tr></thead><tbody>{rows}</tbody></table></div><div data-results='cards' class='asset-card-list' {'hidden' if view != 'cards' or not assets else ''}>{cards}</div><div class='card' data-empty {'hidden' if assets else ''}><p class='muted'>没有符合条件的资产。请更换关键词或清除筛选。</p></div>"
        entries = [{"key": a["name"], "name": str(a["display_name"]).lower(), "category": a["category"], "protocols": [p["name"] for p in a["protocols"]], "tags": a["tags"], "status": a["status"], "status_label": status_info(a["status"])[0], "updated": a.get("updated_at", ""), "sample": is_sample_asset(a), "search": asset_search_text(a)} for a in assets]
        body = f"""<div class='eyebrow'>CATALOG / DESIGN ASSETS</div><h1>设计资产库</h1><p class='muted'>按名称、README、Feature、设计模式、问题索引、分类和协议定位可复用设计资产。</p>
<div class='filter-panel'><form method='get'><input name='q' placeholder='搜索名称、README、Feature 或问题' value='{esc(query.get('q',''))}'><select name='category' aria-label='分类'>{category_options}</select><select name='protocol' aria-label='协议'>{protocol_options}</select><select name='status' aria-label='复用状态'>{status_options}</select><select name='sort' aria-label='排序'>{sort_options}</select><input type='hidden' name='scope' value='{esc(scope)}'><input type='hidden' name='view' value='{esc(view)}'><button>筛选</button></form><div class='filter-footer'><div class='scope-switch'>{scope_links}</div><div><span class='view-switch'>{view_links}</span> <a class='clear-filter' href='/assets'>清除筛选</a></div></div></div>
<div class='result-line' aria-live='polite'><span data-result-count>共 <strong>{len(assets)}</strong> 个结果{'，默认隐藏 '+str(sample_count)+' 个 Sample' if scope == 'library' and sample_count else ''}</span><span class='muted'>状态表示技术复用成熟度，不是项目进度。</span></div>{results}{snapshot_data('assets', entries)}"""
        self.send_bytes(page("Assets", body))

    def asset_page(self, name: str) -> None:
        asset = catalog.get_asset(name)
        if not asset:
            self.send_bytes(page("Not Found", "<h1>资产不存在</h1><p><a href='/assets'>返回资产库</a></p>"), status=HTTPStatus.NOT_FOUND)
            return
        metadata = asset.get("metadata") or {}
        display_metadata = dict(metadata)
        if asset.get("kind") in {"rtl_component", "component"} and isinstance(metadata.get("verification"), dict):
            display_metadata["verification"] = {key: metadata["verification"].get(key) for key in ("simulation", "lint", "synthesis", "last_checked") if key in metadata["verification"]}
        dependencies = "".join(f"<li>{esc(d['dependency_name'])} {esc(d['version_constraint'])} ({esc(d['relation'])})</li>" for d in asset["dependencies"]) or "<li class='muted'>无</li>"
        files = []
        root = Path(asset["root_path"])
        if root.exists():
            files = [str(p.relative_to(root)) for p in sorted(root.rglob("*")) if p.is_file() and p.name not in {"metadata.yaml", "metadata.yml", "metadata.json"}]
        parameters, interfaces, module_name = self.rtl_shape(asset, metadata, files)
        features = metadata.get("features") if isinstance(metadata.get("features"), list) else []
        patterns = metadata.get("design_patterns") if isinstance(metadata.get("design_patterns"), list) else []
        problems = metadata.get("problem_index") if isinstance(metadata.get("problem_index"), list) else []

        readme_content, readme_path = read_asset_readme(root)
        readme_html, toc = render_markdown(readme_content) if readme_content else ("", [])
        toc_html = "".join(f"<a class='{'sub' if level == 3 else ''}' href='#{esc(anchor)}'>{esc(label)}</a>" for level, label, anchor in toc)
        doc_toc = f"<aside class='doc-toc'><strong>文档目录</strong>{toc_html}</aside>" if toc_html else ""
        readme_panel = f"<div class='doc-layout'><article class='markdown-body'>{readme_html}</article>{doc_toc}</div>" if readme_html else "<div class='empty-note'>该资产还没有 README。请在资产目录中添加 <code>README.md</code>。</div>"

        source_files = [file for file in files if not file.lower().endswith("readme.md")]
        source_cards = "".join(
            f"<a class='file-card' href='/assets/{quote(asset['name'])}/file/{quote(file)}'><code>{esc(file)}</code><span class='file-type'>{esc(Path(file).suffix.lstrip('.') or 'text')}</span></a>"
            for file in source_files
        ) or "<div class='empty-note'>未找到本地 RTL 或辅助文件。</div>"

        feature_html = pills(list(features)) if features else "<div class='empty-note'>尚未记录 Feature。</div>"
        pattern_html = " ".join(f"<a class='pill' href='/patterns?q={quote(str(value))}'>{esc(value)}</a>" for value in patterns) if patterns else "<div class='empty-note'>尚未关联设计模式。</div>"
        problem_html = " ".join(f"<a class='pill' href='/problems?q={quote(str(value))}'>{esc(value)}</a>" for value in problems) if problems else "<div class='empty-note'>尚未关联问题索引。</div>"
        limitations = metadata.get("limitations") if isinstance(metadata.get("limitations"), list) else []
        limitation_html = "".join(f"<li>{esc(item)}</li>" for item in limitations) or "<li class='muted'>未记录</li>"
        mapping_section = f"<div class='card' style='margin-top:14px'><h2>Bridge Mapping</h2>{self.mapping_table(asset['mappings'])}</div>" if asset["mappings"] else ""

        label, status_hint, status_style = status_info(asset["status"])
        conclusion = current_conclusion(readme_content)
        banner_text = conclusion or (str(limitations[0]) if limitations else str(asset["description"] or status_hint))
        readiness = f"<div class='readiness-banner {status_style}'><span>{status_badge(asset['status'])}</span><div><strong>{esc(status_hint)}</strong><p>{esc(banner_text)}</p></div></div>"
        version_text = "" if str(asset["version"]).lower() in {"source", "draft", ""} else f"<span>v{esc(asset['version'])}</span>"
        imported = (ASSET_ROOT / "imported").resolve() in Path(asset["root_path"]).resolve().parents
        delete_link = f"<form class='local-only' method='post' action='/assets/{quote(asset['name'])}/delete' onsubmit=\"return confirm('确认删除这个导入资产及其本地 RTL 源码吗？');\"><button type='submit' style='background:#b42318;border-color:#b42318'>删除资产</button></form>" if imported else ""
        example_link = "<a class='secondary-button' href='/examples/axi-channel-slice'>查看设计复盘示例</a>" if asset["name"] == "wql32_axi_slice" else ""
        body = f"""<p><a href='/assets'>← 返回资产库</a></p>
<div class='asset-header'><div><div class='asset-kicker'><span class='eyebrow'>DESIGN ASSET</span>{status_badge(asset['status'])}</div><h1>{esc(asset['display_name'])}</h1><div class='asset-subline'><code>{esc(asset['name'])}</code>{version_text}<span>{esc(asset['category'])}</span></div></div><div class='asset-actions'>{example_link}<a class='secondary-button local-only' href='/assets/{quote(asset['name'])}/edit'>编辑资产信息</a><a class='secondary-button local-only' href='/assets/{quote(asset['name'])}/readme/edit'>编辑 README</a>{delete_link}</div></div>
{readiness}
<div class='grid'><div class='card'><h3>用途</h3><p>{esc(asset['description']) or '—'}</p></div><div class='card'><h3>协议</h3><p>{pills([p['name'] for p in asset['protocols']])}</p></div><div class='card'><h3>标签</h3><p>{pills(asset['tags'])}</p></div></div>
<section data-tabs><div class='asset-tabs' role='tablist' aria-label='资产详情'><button class='asset-tab' type='button' role='tab' aria-selected='true' data-tab='asset-doc'>设计说明</button><button class='asset-tab' type='button' role='tab' aria-selected='false' data-tab='asset-interface'>接口</button><button class='asset-tab' type='button' role='tab' aria-selected='false' data-tab='asset-source'>源码</button><button class='asset-tab' type='button' role='tab' aria-selected='false' data-tab='asset-knowledge'>设计知识</button></div>
<div class='tab-panel' id='asset-doc' role='tabpanel'>{readme_panel}</div>
<div class='tab-panel' id='asset-interface' role='tabpanel' hidden><div class='card'><div class='section-title'><h2>RTL Interface</h2></div><p class='muted'>Module <code>{esc(module_name)}</code> · {len(parameters)} parameters · {len(interfaces)} ports</p><h3>Parameters</h3>{self.parameter_table(parameters)}<h3 style='margin-top:22px'>Ports</h3>{self.interface_table(interfaces)}</div></div>
<div class='tab-panel' id='asset-source' role='tabpanel' hidden><div class='document-toolbar'><div><h2 style='margin:0'>本地文件</h2><span class='muted'>点击文件进入带行号的阅读视图</span></div></div><div class='file-grid'>{source_cards}</div></div>
<div class='tab-panel' id='asset-knowledge' role='tabpanel' hidden><div class='knowledge-grid'><div class='card'><h3>Features</h3>{feature_html}</div><div class='card'><h3>Design Patterns</h3>{pattern_html}</div><div class='card'><h3>Problem Index</h3>{problem_html}</div></div><div class='card' style='margin-top:14px'><h2>使用限制</h2><ul>{limitation_html}</ul><h2>依赖</h2><ul>{dependencies}</ul></div>{mapping_section}</div></section>
<details class='card advanced'><summary>Advanced Metadata</summary><p class='muted'>原始 metadata 配置，仅用于调试、脚本处理和 schema 检查。</p><pre>{esc(json.dumps(display_metadata, ensure_ascii=False, indent=2))}</pre></details>"""
        self.send_bytes(page(asset["display_name"], body))

    def mapping_table(self, mappings: list[dict[str, object]]) -> str:
        if not mappings:
            return "<p class='muted'>该资产暂无 transaction mapping。</p>"
        rows = "".join(
            f"<tr><td><code>{esc(m['source_transaction'])}</code></td><td>→</td><td><code>{esc(m['target_transaction'])}</code></td><td>{esc(m['ordering'])}</td><td>{esc(m['split_behavior'])}</td><td>{'是' if m['response_required'] else '否'}</td><td>{esc(m['error_mapping'])}</td><td>{esc(json.dumps(m['field_mapping'], ensure_ascii=False))}</td></tr>"
            for m in mappings
        )
        return f"<table><tr><th>Source</th><th></th><th>Target</th><th>Ordering</th><th>Split</th><th>Response</th><th>Error Mapping</th><th>Field Mapping</th></tr>{rows}</table>"

    def verification_table(self, results: list[dict[str, object]]) -> str:
        if not results:
            return "<p class='muted'>暂无验证记录。</p>"
        rows = "".join(f"<tr><td>{esc(r['check_type'])}</td><td class={'ok' if r['status']=='passed' else 'danger' if r['status']=='failed' else ''}>{esc(r['status'])}</td><td>{esc(r['checked_at']) or '—'}</td><td>{esc(r['notes']) or '—'}</td></tr>" for r in results)
        return f"<table><tr><th>Check</th><th>Status</th><th>Checked</th><th>Notes</th></tr>{rows}</table>"

    def verification_page(self) -> None:
        rows_data = catalog.verification_summary()
        rows = "".join(f"<tr><td><a href='/assets/{quote(r['name'])}'>{esc(r['display_name'])}</a></td><td>{esc(r['category'])}</td><td>{esc(r['check_type']) or '—'}</td><td class={'ok' if r['status']=='passed' else 'danger' if r['status']=='failed' else ''}>{esc(r['status']) or '—'}</td><td>{esc(r['checked_at']) or '—'}</td></tr>" for r in rows_data)
        body = f"<h1>Verification Matrix</h1><p class='muted'>查看每个资产的仿真、lint、CDC、formal、综合和性能检查状态。</p><table><tr><th>Asset</th><th>Category</th><th>Check</th><th>Status</th><th>Checked</th></tr>{rows or '<tr><td colspan=5 class=muted>暂无验证记录</td></tr>'}</table>"
        self.send_bytes(page("Verification", body))

    def dependencies_page(self) -> None:
        graph = catalog.dependency_graph()
        rows = "".join(f"<tr><td><a href='/assets/{quote(e['asset_name'])}'>{esc(e['asset_name'])}</a></td><td>{esc(e['dependency_name'])}</td><td>{esc(e['version_constraint']) or '—'}</td><td>{esc(e['relation'])}</td></tr>" for e in graph['edges'])
        missing = pills(graph['missing_dependencies'])
        body = f"<h1>Dependencies</h1><div class='card'><h3>Missing dependencies</h3><p>{missing}</p></div><table><tr><th>Asset</th><th>Dependency</th><th>Version</th><th>Relation</th></tr>{rows or '<tr><td colspan=4 class=muted>暂无依赖关系</td></tr>'}</table>"
        self.send_bytes(page("Dependencies", body))

    def report_page(self) -> None:
        assets = [asset for asset in catalog.list_assets() if not is_sample_asset(asset)]
        gap_rows: list[str] = []
        documented = 0
        knowledge_complete = 0
        for asset in assets:
            metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
            readme, _path = read_asset_readme(Path(str(asset["root_path"])))
            gaps: list[str] = []
            if not readme.strip():
                gaps.append("缺少 README")
            else:
                documented += 1
            if not metadata.get("features"):
                gaps.append("Feature 未记录")
            if not metadata.get("design_patterns"):
                gaps.append("设计模式未关联")
            if not metadata.get("problem_index"):
                gaps.append("问题索引未关联")
            if metadata.get("features") and metadata.get("design_patterns") and metadata.get("problem_index"):
                knowledge_complete += 1
            if str(asset["status"]) == "needs_fix":
                gaps.insert(0, "RTL 需要修复")
            if gaps:
                tags = "".join(f"<span class='category-label'>{esc(gap)}</span>" for gap in gaps)
                gap_rows.append(f"<div class='gap-row'><div><a href='/assets/{quote(asset['name'])}'><strong>{esc(asset['display_name'])}</strong></a><br><code>{esc(asset['name'])}</code></div><div class='gap-tags'>{tags}</div><a class='secondary-button local-only' href='/assets/{quote(asset['name'])}/edit'>完善信息</a><a class='secondary-button snapshot-only' href='/import'>本地维护说明</a></div>")
        needs_fix = sum(1 for asset in assets if str(asset["status"]) == "needs_fix")
        constrained = sum(1 for asset in assets if str(asset["status"]) == "constrained")
        body = f"""<div class='eyebrow'>LIBRARY / KNOWLEDGE GAPS</div><h1>待完善项</h1><p class='muted'>只关注资产能否被正确理解和安全复用，不跟踪项目进度或验证管理。</p><div class='stat-grid'><div class='card stat-card'><div class='eyebrow'>DOCUMENTED</div><div class='stat-value'>{documented}/{len(assets)}</div><div class='stat-label'>已有本地 README</div></div><div class='card stat-card'><div class='eyebrow'>KNOWLEDGE LINKED</div><div class='stat-value'>{knowledge_complete}/{len(assets)}</div><div class='stat-label'>Feature、模式和问题均已关联</div></div><div class='card stat-card'><div class='eyebrow'>NEEDS FIX</div><div class='stat-value'>{needs_fix}</div><div class='stat-label'>RTL 修复后再复用</div></div><div class='card stat-card'><div class='eyebrow'>CONSTRAINED</div><div class='stat-value'>{constrained}</div><div class='stat-label'>满足约束后复用</div></div></div><div class='section-title'><h2>建议处理顺序</h2></div><div class='gap-list'>{''.join(gap_rows) or '<div class="card ok">当前资产都已完成基础知识整理。</div>'}</div>"""
        self.send_bytes(page("待完善项", body))

    def rtl_template_page(self) -> None:
        try:
            source = RTL_TEMPLATE_PATH.read_text(encoding="utf-8")
        except OSError as exc:
            self.send_bytes(
                page("RTL模块设计与复盘模板", f"<h1>模板加载失败</h1><p>{esc(exc)}</p>"),
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        document, toc = render_markdown(source)
        toc_html = "".join(
            f"<a class='{'sub' if level == 3 else ''}' href='#{esc(anchor)}'>{esc(label)}</a>"
            for level, label, anchor in toc
        )
        toc_panel = f"<aside class='doc-toc'><strong>模板目录</strong>{toc_html}</aside>" if toc_html else ""
        chapters = [
            ("1. 模块概述", "功能、应用场景、设计目标与非目标"),
            ("2. 接口定义", "时钟、复位、输入输出、握手与稳定性约束"),
            ("3. 架构设计", "数据通路、控制通路、状态机与不变式"),
            ("4. 关键 RTL 实现", "核心逻辑、参数化、边界处理与实现取舍"),
            ("5. 时序与性能", "关键路径、吞吐率、延迟、面积与功耗权衡"),
            ("6. 验证方案", "基本场景、边界与并发、断言、覆盖与结果证据"),
            ("7. 设计经验与复盘", "问题、根因、解决方法、可改进点与复用结论"),
        ]
        chapter_rows = "".join(f"<tr><td>{esc(name)}</td><td>{esc(detail)}</td></tr>" for name, detail in chapters)
        body = f"""<section class='hero template-hero'><div class='eyebrow'>KNOWLEDGE TEMPLATE / RTL DESIGN</div><h1>RTL模块设计与复盘模板</h1><p class='template-intro'>用一套固定的工程结构，记录模块为什么这样设计、RTL 如何实现、如何证明它在边界条件下仍然正确，以及下次复用时必须知道什么。</p><div class='hero-actions'><a class='hero-button' href='#template-body'>阅读完整模板</a><button class='copy-button' type='button' data-copy-target='#rtl-template-source'>复制 Markdown 模板</button><a class='hero-link' href='/examples/axi-channel-slice'>查看 AXI Channel Slice 填写示例 →</a></div></section>
<div class='section-title'><h2>怎样使用这份模板</h2></div><div class='template-workflow'><article class='card template-step'><span class='template-step-number'>01</span><h3>设计前</h3><p>先写清目标、非目标、接口契约和架构不变式，作为 RTL 实现的输入。</p></article><article class='card template-step'><span class='template-step-number'>02</span><h3>实现中</h3><p>同步补充核心逻辑、边界处理和性能取舍，让文档与代码决策保持一致。</p></article><article class='card template-step'><span class='template-step-number'>03</span><h3>验证后</h3><p>用可复查的测试、断言和问题根因更新结论，沉淀成下一个模块可复用的经验。</p></article></div>
<div class='section-title'><h2>章节总览</h2></div><table class='template-overview'><thead><tr><th>章节</th><th>需要记录的内容</th></tr></thead><tbody>{chapter_rows}</tbody></table>
<div class='section-title'><h2>完整模板</h2></div><div class='template-actions'><p class='muted'>保留可证明的事实；未定义的协议语义、位宽和性能数据应明确标记为待确认。</p><button class='copy-button' type='button' data-copy-target='#rtl-template-source'>复制</button></div><div class='doc-layout' id='template-body'><article class='markdown-body'>{document}</article>{toc_panel}</div>
<details class='card template-copy-panel'><summary>查看可复制的 Markdown 源文</summary><pre><code id='rtl-template-source'>{esc(source)}</code></pre></details>"""
        self.send_bytes(page("RTL模块设计与复盘模板", body))

    def axi_slice_example_page(self) -> None:
        try:
            source = AXI_SLICE_EXAMPLE_PATH.read_text(encoding="utf-8")
        except OSError as exc:
            self.send_bytes(
                page("AXI Channel Slice 设计复盘示例", f"<h1>示例加载失败</h1><p>{esc(exc)}</p>"),
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        document, toc = render_markdown(source)
        toc_html = "".join(
            f"<a class='{'sub' if level == 3 else ''}' href='#{esc(anchor)}'>{esc(label)}</a>"
            for level, label, anchor in toc
        )
        toc_panel = f"<aside class='doc-toc'><strong>示例目录</strong>{toc_html}</aside>" if toc_html else ""
        body = f"""<p><a href='/templates/rtl-module-design-review'>← 返回 RTL 模块设计与复盘模板</a></p>
<section class='hero template-hero'><div class='eyebrow'>DESIGN REVIEW / WORKED EXAMPLE</div><h1>AXI Channel Slice</h1><p class='template-intro'>以站点中现有的双槽 ready/valid 切片为例，把设计结构、握手边界、性能推导和待验证项写成可复查的七章记录。</p><div class='hero-actions'><a class='hero-button' href='#example-body'>阅读设计复盘</a><a class='hero-link' href='/assets/wql32_axi_slice'>查看资产与源码 →</a></div></section>
<div class='template-actions'><p class='muted'>静态源码分析示例；验证状态以资产 metadata 为准。</p><button class='copy-button' type='button' data-copy-target='#axi-slice-example-source'>复制 Markdown 示例</button></div>
<div class='doc-layout' id='example-body'><article class='markdown-body'>{document}</article>{toc_panel}</div>
<details class='card template-copy-panel'><summary>查看 Markdown 源文</summary><pre><code id='axi-slice-example-source'>{esc(source)}</code></pre></details>"""
        self.send_bytes(page("AXI Channel Slice 设计复盘示例", body))

    def index_data(self, field: str, query: str = "") -> list[dict[str, object]]:
        grouped: dict[str, list[dict[str, str]]] = {}
        needle = query.strip().lower()
        for asset in catalog.list_assets():
            metadata = asset.get("metadata") or {}
            values = metadata.get(field) if isinstance(metadata.get(field), list) else []
            if not values and field == "design_patterns":
                pattern_map = {"fifo": "FIFO buffering", "cdc": "Clock-domain crossing", "arbiter": "Round-robin arbitration", "codec": "One-hot encoding", "storage": "State storage"}
                values = [pattern_map.get(str(asset.get("category")), "")]
            if not values and field == "problem_index":
                asset_name = str(asset.get("name", "")).lower()
                category = str(asset.get("category", "")).lower()
                problem_map = {
                    "fifo": "FIFO boundary, reset and overflow behavior",
                    "cdc": "Reset release and cross-domain synchronization",
                    "arbiter": "Fairness, starvation and grant timing",
                    "codec": "Invalid one-hot input and priority behavior",
                    "storage": "Read/write collision and state retention",
                    "axi": "Ready/valid backpressure and channel independence",
                    "bridges_pcie": "PCIe completion ordering and tag tracking",
                    "bridges_cxl": "CXL/AXI ordering and coherency policy",
                }
                key = "bridges_pcie" if category == "bridges" and "pcie" in asset_name else "bridges_cxl" if category == "bridges" and "cxl" in asset_name else category
                values = [problem_map.get(key, "")]
            for value in values:
                label = str(value).strip()
                if not label or (needle and needle not in label.lower()):
                    continue
                grouped.setdefault(label, []).append({"name": str(asset["name"]), "display_name": str(asset["display_name"])})
        return [{"name": label, "assets": sorted(items, key=lambda item: item["display_name"])} for label, items in sorted(grouped.items(), key=lambda item: item[0].lower())]

    def index_page(self, title: str, eyebrow: str, field: str, query: dict[str, str], description: str) -> None:
        guide = PATTERN_GUIDE if field == "design_patterns" else PROBLEM_GUIDE
        entries = self.index_data(field)
        needle = query.get("q", "").strip().lower()
        if needle:
            entries = [entry for entry in entries if needle in " ".join([str(entry["name"]), guide.get(str(entry["name"]).lower(), ("", []))[0], *guide.get(str(entry["name"]).lower(), ("", []))[1]]).lower()]
        card_items = []
        for entry in entries:
            assets = " ".join(f"<a class='pill' href='/assets/{quote(item['name'])}'>{esc(item['display_name'])}</a>" for item in entry["assets"])
            summary, checks = guide.get(str(entry["name"]).lower(), ("该索引项尚未补充独立说明，可先从关联资产的 README 和限制中整理经验。", []))
            check_html = "".join(f"<li>{esc(item)}</li>" for item in checks) or "<li>补充适用条件、边界情况和验证检查点。</li>"
            card_items.append(f"<article class='knowledge-card' data-entry='{esc(entry['name'])}'><header><h2>{esc(entry['name'])}</h2><span class='index-count'>{len(entry['assets'])} 个资产</span></header><p>{esc(summary)}</p><div class='asset-links'><strong>关联资产</strong>{assets}</div><details><summary>设计关注点</summary><ul>{check_html}</ul></details><footer><span class='local-only'>关联关系可在任一资产的“编辑资产信息”页面中维护。</span><span class='snapshot-only'>关联关系通过本地服务维护，<a href='/import'>查看维护方式</a>。</span></footer></article>")
        cards = "".join(card_items)
        empty = f"<div class='card' data-empty {'hidden' if entries else ''}><p class='muted'>没有符合条件的索引项。请更换关键词或清除搜索。</p></div>"
        search_entries = [{"key": entry["name"], "search": " ".join([str(entry["name"]), guide.get(str(entry["name"]).lower(), ("", []))[0], *guide.get(str(entry["name"]).lower(), ("", []))[1]]).lower()} for entry in entries]
        body = f"<div class='eyebrow'>{esc(eyebrow)}</div><div class='asset-header'><div><h1>{esc(title)}</h1><p class='muted'>{esc(description)}</p></div><a class='secondary-button local-only' href='/assets?view=cards'>选择资产并维护关联</a><a class='secondary-button snapshot-only' href='/assets?view=cards'>浏览关联资产</a></div><div class='filter-panel'><form method='get' style='grid-template-columns:minmax(260px,1fr) auto'><input name='q' placeholder='搜索名称、说明或关注点' value='{esc(query.get('q', ''))}'><button>搜索</button><a class='clear-filter' href='/{'patterns' if field == 'design_patterns' else 'problems'}'>清除搜索</a></form></div><div class='result-line' aria-live='polite'><span data-result-count>共 <strong>{len(entries)}</strong> 个索引项</span><span class='muted'>内容用于设计复用与问题排查，不表示项目状态。</span></div><div class='knowledge-list' data-results='items'>{cards}</div>{empty}{snapshot_data('index', search_entries)}"
        self.send_bytes(page(title, body))

    def patterns_page(self, query: dict[str, str]) -> None:
        self.index_page("Design Patterns", "PATTERN LIBRARY", "design_patterns", query, "按可复用的 RTL / DMA / 协议设计模式组织资产。")

    def problems_page(self, query: dict[str, str]) -> None:
        self.index_page("Problem Index", "ENGINEERING PROBLEMS", "problem_index", query, "按设计问题和 corner case 反查相关资产与经验。")

    def protocols_page(self) -> None:
        protocols = catalog.protocols()
        rows = "".join(f"<tr><td><code>{esc(p['name'])}</code></td><td>{esc(p['direction']) or '—'}</td><td>{p['asset_count']}</td></tr>" for p in protocols)
        body = f"<h1>Protocols</h1><p class='muted'>协议是资产、Bridge mapping 和 Debug case 的共同索引。</p><table><tr><th>协议</th><th>方向</th><th>关联资产</th></tr>{rows or '<tr><td colspan=3 class=muted>暂无协议数据</td></tr>'}</table>"
        self.send_bytes(page("Protocols", body))

    def mappings_page(self, query: dict[str, str]) -> None:
        mappings = catalog.mappings()
        needle = query.get("q", "").strip().lower()
        if needle:
            mappings = [mapping for mapping in mappings if needle in " ".join(str(mapping.get(field, "")) for field in ("asset_name", "display_name", "source_transaction", "target_transaction")).lower()]
        def source_protocol(mapping: dict[str, object]) -> str:
            transaction = str(mapping.get("source_transaction", "")).lower()
            if transaction.startswith("pcie"):
                return "PCIe"
            if transaction.startswith("cxl"):
                return "CXL"
            if transaction.startswith("axi"):
                return "AXI"
            return "Other"

        def direction(mapping: dict[str, object]) -> str:
            text = f"{mapping.get('source_transaction', '')} {mapping.get('target_transaction', '')}".lower()
            return "write" if "write" in text else "read" if "read" in text else "other"

        selected_source = query.get("source", "")
        selected_direction = query.get("direction", "")
        selected_response = query.get("response", "")
        if selected_source:
            mappings = [mapping for mapping in mappings if source_protocol(mapping) == selected_source]
        if selected_direction:
            mappings = [mapping for mapping in mappings if direction(mapping) == selected_direction]
        if selected_response:
            expected = selected_response == "required"
            mappings = [mapping for mapping in mappings if bool(mapping.get("response_required")) == expected]
        cards = []
        for mapping in mappings:
            fields = mapping.get("field_mapping") or []
            field_rows = "".join(f"<tr><td><code>{esc(item.get('source', ''))}</code></td><td>→</td><td><code>{esc(item.get('target', ''))}</code></td><td>{esc(item.get('rule', ''))}</td></tr>" for item in fields if isinstance(item, dict))
            field_detail = f"<table><tr><th>Source Field</th><th></th><th>Target Field</th><th>Rule</th></tr>{field_rows}</table>" if field_rows else "<p class='muted'>未记录 field mapping。</p>"
            sample = "<span class='sample-mark'>sample</span>" if "sample" in f"{mapping['asset_name']} {mapping['display_name']}".lower() else ""
            cards.append(f"<article class='card mapping-card' data-entry='{mapping['id']}'><div class='mapping-head'><div><a class='mapping-asset' href='/assets/{quote(mapping['asset_name'])}'>{esc(mapping['display_name'])}</a> {sample}</div><span class='category-label'>{source_protocol(mapping)} → AXI</span></div><div class='transaction-flow'><div class='flow-node'><small>Source transaction</small><code>{esc(mapping['source_transaction'])}</code></div><div class='flow-arrow'>→</div><div class='flow-node bridge'><small>Bridge policy</small><strong>{esc(mapping['ordering']) or 'ordering 未记录'}</strong></div><div class='flow-arrow'>→</div><div class='flow-node'><small>Target transaction</small><code>{esc(mapping['target_transaction'])}</code></div></div><div class='mapping-badges'><span class='mapping-badge'><strong>Split</strong> {esc(mapping['split_behavior']) or '未记录'}</span><span class='mapping-badge'><strong>Response</strong> {'required' if mapping['response_required'] else 'not required'}</span><span class='mapping-badge'><strong>Direction</strong> {direction(mapping)}</span></div><details class='mapping-detail'><summary>字段映射、错误路径与补充规则</summary>{field_detail}<p><strong>Error Mapping:</strong> {esc(mapping['error_mapping']) or '—'}</p><p><strong>Notes:</strong> {esc(mapping.get('notes')) or '—'}</p></details></article>")

        def option(value: str, label: str, selected: str) -> str:
            return f"<option value='{esc(value)}' {'selected' if value == selected else ''}>{esc(label)}</option>"

        source_options = option("", "全部源协议", selected_source) + "".join(option(value, value, selected_source) for value in ("PCIe", "CXL", "AXI", "Other"))
        direction_options = option("", "全部方向", selected_direction) + option("read", "Read", selected_direction) + option("write", "Write", selected_direction) + option("other", "Other", selected_direction)
        response_options = option("", "全部响应类型", selected_response) + option("required", "需要 Response", selected_response) + option("not_required", "不需要 Response", selected_response)
        sample_count = sum(1 for mapping in mappings if "sample" in f"{mapping['asset_name']} {mapping['display_name']}".lower())
        sample_notice = f"<div class='readiness-banner info'><span class='sample-mark'>sample</span><div><strong>当前 {sample_count} 条规则来自 Generic Sample</strong><p>结构已经可以承载真实 PCIe/CXL 到 AXI 事务规则；后续应逐步用你的实际 Bridge 设计经验替换示例内容。</p></div></div>" if mappings and sample_count == len(mappings) else ""
        entries = [{"key": str(mapping["id"]), "search": " ".join(str(mapping.get(field, "")) for field in ("asset_name", "display_name", "source_transaction", "target_transaction")).lower(), "source": source_protocol(mapping), "direction": direction(mapping), "response": "required" if mapping["response_required"] else "not_required"} for mapping in mappings]
        empty = f"<div class='card' data-empty {'hidden' if mappings else ''}><p class='muted'>暂无符合条件的 mapping 数据。请更换条件或清除筛选。</p></div>"
        body = f"<div class='eyebrow'>PROTOCOL TRANSLATION</div><h1>Bridge Mappings</h1><p class='muted'>以事务流为中心查看 PCIe/CXL 与 AXI 之间的转换、顺序、拆分和响应规则。</p>{sample_notice}<div class='filter-panel'><form method='get' style='grid-template-columns:minmax(220px,2fr) repeat(3,minmax(150px,1fr)) auto'><input name='q' placeholder='搜索 Bridge 或 transaction' value='{esc(query.get('q',''))}'><select name='source' aria-label='源协议'>{source_options}</select><select name='direction' aria-label='方向'>{direction_options}</select><select name='response' aria-label='响应类型'>{response_options}</select><button>筛选</button><a class='clear-filter' href='/mappings'>清除筛选</a></form></div><div class='result-line' aria-live='polite'><span data-result-count>共 <strong>{len(mappings)}</strong> 条 mapping</span><span class='muted'>展开卡片查看字段映射与错误路径。</span></div><div class='mapping-list' data-results='items'>{''.join(cards)}</div>{empty}{snapshot_data('mappings', entries)}"
        self.send_bytes(page("Bridge Mappings", body))

    def file_page(self, name: str, relative_file: str) -> None:
        asset = catalog.get_asset(name)
        if not asset:
            self.send_bytes(page("Not Found", "<h1>资产不存在</h1>"), status=HTTPStatus.NOT_FOUND)
            return
        root = Path(asset["root_path"]).resolve()
        candidate = (root / relative_file).resolve()
        if root not in candidate.parents or not candidate.is_file():
            self.send_bytes(page("Not Found", "<h1>文件不存在</h1><p>文件必须位于资产目录内。</p>"), status=HTTPStatus.NOT_FOUND)
            return
        if candidate.stat().st_size > 1024 * 1024:
            self.send_bytes(page("File Too Large", "<h1>文件过大</h1><p>当前版本只允许查看 1 MiB 以内的文本文件。</p>"), status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        try:
            content = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            self.send_bytes(page("Unsupported File", "<h1>暂不支持该文件</h1><p>当前版本只查看 UTF-8 文本文件。</p>"), status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return
        line_count = content.count("\n") + 1
        is_markdown = candidate.suffix.lower() in {".md", ".markdown"}
        if is_markdown:
            document, toc = render_markdown(content)
            toc_html = "".join(f"<a class='{'sub' if level == 3 else ''}' href='#{esc(anchor)}'>{esc(label)}</a>" for level, label, anchor in toc)
            toc_panel = f"<aside class='doc-toc'><strong>文档目录</strong>{toc_html}</aside>" if toc_html else ""
            viewer = f"<div class='doc-layout'><article class='markdown-body'>{document}</article>{toc_panel}</div>"
            eyebrow = "DOCUMENT / README"
        else:
            code_lines = highlight_verilog(content)
            language = "SystemVerilog" if candidate.suffix.lower() in {".sv", ".svh"} else "Verilog"
            viewer = f"<div class='code-frame'><div class='code-header'><span>{esc(candidate.name)}</span><span class='language'>{language}</span></div><pre><code class='source-code' id='source-code'>{code_lines}</code></pre></div>"
            eyebrow = "SOURCE / RTL FILE"
        copy_action = "" if is_markdown else "<button class='copy-button' type='button' data-copy-target='#source-code'>复制</button>"
        body = f"""<p><a href='/assets/{quote(asset['name'])}'>← {esc(asset['display_name'])}</a></p>
<div class='eyebrow'>{eyebrow}</div><h1>{esc(relative_file)}</h1><div class='document-toolbar'><strong>{esc(asset['name'])}</strong><div class='actions'><span class='muted'>{line_count} lines · {candidate.stat().st_size} bytes · UTF-8</span>{copy_action}</div></div>{viewer}"""
        self.send_bytes(page(relative_file, body))


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    catalog.scan()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"System IP Design Hub running at http://{host}:{port}")
    print(f"Asset root: {ASSET_ROOT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
