/**
 * 搜索工具 - 使用 Wikipedia API 获取搜索结果
 */

interface SearchResult {
  title: string;
  href: string;
  body: string;
}

export async function search(args: { query: string; max_results?: number }): Promise<SearchResult[]> {
  const maxResults = args.max_results ?? 5;

  // 尝试多个语言版本的 Wikipedia
  const languages = ["zh", "en"];

  for (const lang of languages) {
    try {
      const results = await searchWithLang(args.query, maxResults, lang);
      if (results.length > 0) {
        return results;
      }
    } catch (error) {
      console.error(`Wikipedia ${lang} search failed:`, error);
    }
  }

  return [];
}

async function searchWithLang(query: string, maxResults: number, lang: string): Promise<SearchResult[]> {
  // 使用 Wikipedia opensearch API 搜索
  const url = `https://${lang}.wikipedia.org/w/api.php?action=opensearch&search=${encodeURIComponent(query)}&limit=${maxResults}&format=json`;
  const response = await fetch(url);

  if (!response.ok) {
    console.error(`Wikipedia ${lang} API error:`, response.status);
    return [];
  }

  const data = await response.json() as [string, string[], string[], string[]];
  const titles = data[1];
  const urls = data[3];

  if (!titles || titles.length === 0) {
    return [];
  }

  // 获取每个结果的摘要
  const results: SearchResult[] = [];
  for (let i = 0; i < titles.length; i++) {
    const body = await getExtract(titles[i], lang);
    results.push({ title: titles[i], href: urls[i], body });
  }

  return results;
}

async function getExtract(title: string, lang: string): Promise<string> {
  try {
    const url = `https://${lang}.wikipedia.org/w/api.php?action=query&titles=${encodeURIComponent(title)}&prop=extracts&exintro=true&format=json`;
    const response = await fetch(url);

    if (!response.ok) {
      return "";
    }

    const data = await response.json() as any;
    const pages = data.query?.pages;
    const pageId = Object.keys(pages)[0];
    const extract = pages[pageId]?.extract ?? "";
    // 去除HTML标签和多余空白，截取前200字符
    return extract.replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim().substring(0, 200);
  } catch {
    return "";
  }
}
