import { NextRequest, NextResponse } from "next/server";

/** 新号段 YYMM + 至少 4 位序号，可选 vN（arXiv 序号位数会随稿件量增长） */
const ARXIV_NEW_ID_RE = /^\d{4}\.\d{4,}(v\d+)?$/i;

/**
 * 同源 PDF 代理，供 react-pdf / pdf.js 使用。
 * pdf.js 会发 Range 分段请求；必须把 Range 原样转给 arXiv 并回传 206 + Content-Range，
 * 否则部分环境下会出现 “Missing PDF” / 预览失败。浏览器直接打开官方链接则不受此影响。
 */
export async function GET(
  req: NextRequest,
  context: { params: { arxivId: string } }
) {
  const raw = decodeURIComponent(context.params.arxivId ?? "").trim();
  const arxivId = raw.replace(/\.pdf$/i, "");

  if (!ARXIV_NEW_ID_RE.test(arxivId)) {
    return NextResponse.json({ error: "无效的 arXiv ID 格式" }, { status: 400 });
  }

  const upstream = `https://arxiv.org/pdf/${arxivId}.pdf`;
  const range = req.headers.get("range");

  const upstreamHeaders = new Headers({
    Accept: "application/pdf,*/*;q=0.8",
    "User-Agent":
      "Mozilla/5.0 (compatible; ArxPrism/1.0; academic paper preview)",
  });
  if (range) upstreamHeaders.set("Range", range);

  let res: Response;
  try {
    res = await fetch(upstream, {
      redirect: "follow",
      cache: "no-store",
      headers: upstreamHeaders,
    });
  } catch (e) {
    return NextResponse.json(
      {
        error: e instanceof Error ? e.message : "无法连接 arXiv",
        upstream,
      },
      { status: 502 }
    );
  }

  if (!res.ok) {
    return NextResponse.json(
      {
        error:
          res.status === 404
            ? "arXiv 上暂无该 PDF（ID 可能错误、未发布或已撤稿）"
            : `arXiv 返回 HTTP ${res.status}`,
        upstream,
      },
      { status: res.status === 404 ? 404 : 502 }
    );
  }

  const ct = res.headers.get("content-type") ?? "";
  const isPdf =
    ct.includes("application/pdf") ||
    ct.includes("application/octet-stream");

  if (!isPdf || !res.body) {
    const buf = await res.arrayBuffer();
    const head = new TextDecoder().decode(
      buf.slice(0, Math.min(400, buf.byteLength))
    );
    if (
      head.trimStart().toLowerCase().startsWith("<!doctype") ||
      head.trimStart().startsWith("<html")
    ) {
      return NextResponse.json(
        { error: "arXiv 返回了网页而非 PDF（通常为 404 页面）", upstream },
        { status: 404 }
      );
    }
    return NextResponse.json(
      { error: "响应不是有效的 PDF", upstream },
      { status: 502 }
    );
  }

  const out = new Headers();
  out.set("Content-Type", "application/pdf");
  const contentRange = res.headers.get("content-range");
  if (contentRange) out.set("Content-Range", contentRange);
  const acceptRanges = res.headers.get("accept-ranges");
  if (acceptRanges) out.set("Accept-Ranges", acceptRanges);
  const contentLength = res.headers.get("content-length");
  if (contentLength) out.set("Content-Length", contentLength);
  out.set("Cache-Control", "public, max-age=3600, s-maxage=3600");

  return new NextResponse(res.body, {
    status: res.status,
    headers: out,
  });
}
