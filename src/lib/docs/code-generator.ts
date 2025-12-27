/**
 * Multi-language code example generator for API documentation
 */

export interface APIRequest {
  method: string;
  path: string;
  authType: "user" | "admin" | "none";
  headers?: Record<string, string>;
  query?: Record<string, string>;
  body?: unknown;
  description?: string;
}

export interface CodeExample {
  language: string;
  label: string;
  code: string;
}

function getBaseUrl(authType: "user" | "admin" | "none"): string {
  if (typeof window !== "undefined") {
    // Client-side: use environment variable or default
    const apiUrl = process.env.NEXT_PUBLIC_VEXA_API_URL || "https://api.vexa.ai";
    const adminApiUrl = process.env.NEXT_PUBLIC_VEXA_ADMIN_API_URL || "https://api.vexa.ai";
    return authType === "admin" ? adminApiUrl : apiUrl;
  }
  // Server-side: use defaults
  return authType === "admin" ? "https://api.vexa.ai" : "https://api.vexa.ai";
}

function getAuthHeader(authType: "user" | "admin" | "none"): string {
  switch (authType) {
    case "user":
      return "X-API-Key: YOUR_API_KEY";
    case "admin":
      return "X-Admin-API-Key: YOUR_ADMIN_API_KEY";
    default:
      return "";
  }
}

function formatJson(obj: unknown, indent = 2): string {
  return JSON.stringify(obj, null, indent);
}

function buildQueryString(query?: Record<string, string>): string {
  if (!query || Object.keys(query).length === 0) return "";
  const params = new URLSearchParams(query);
  return `?${params.toString()}`;
}

export function generateCurl(request: APIRequest): string {
  const baseUrl = getBaseUrl(request.authType);
  const url = `${baseUrl}${request.path}${buildQueryString(request.query)}`;
  const authHeader = getAuthHeader(request.authType);
  
  let curl = `curl -X ${request.method.toUpperCase()} "${url}"`;
  
  if (authHeader) {
    curl += ` \\\n  -H "${authHeader}"`;
  }
  
  if (request.headers) {
    Object.entries(request.headers).forEach(([key, value]) => {
      curl += ` \\\n  -H "${key}: ${value}"`;
    });
  }
  
  if (request.body) {
    curl += ` \\\n  -H "Content-Type: application/json"`;
    curl += ` \\\n  -d '${formatJson(request.body)}'`;
  }
  
  return curl;
}

export function generateJavaScript(request: APIRequest): string {
  const baseUrl = getBaseUrl(request.authType);
  const url = `${baseUrl}${request.path}${buildQueryString(request.query)}`;
  const authHeader = getAuthHeader(request.authType);
  
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...request.headers,
  };
  
  if (authHeader) {
    const [key, value] = authHeader.split(": ");
    headers[key] = value;
  }
  
  const options: Record<string, unknown> = {
    method: request.method.toUpperCase(),
    headers,
  };
  
  if (request.body) {
    options.body = JSON.stringify(request.body);
  }
  
  const optionsStr = formatJson(options, 2).replace(/"YOUR_API_KEY"/g, "process.env.VEXA_API_KEY").replace(/"YOUR_ADMIN_API_KEY"/g, "process.env.VEXA_ADMIN_API_KEY");
  
  return `const response = await fetch("${url}", ${optionsStr});\nconst data = await response.json();`;
}

export function generatePython(request: APIRequest): string {
  const baseUrl = getBaseUrl(request.authType);
  const url = `${baseUrl}${request.path}${buildQueryString(request.query)}`;
  const authHeader = getAuthHeader(request.authType);
  
  let code = "import requests\n\n";
  
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...request.headers,
  };
  
  if (authHeader) {
    const [key, value] = authHeader.split(": ");
    headers[key] = value.replace("YOUR_API_KEY", "os.getenv('VEXA_API_KEY')").replace("YOUR_ADMIN_API_KEY", "os.getenv('VEXA_ADMIN_API_KEY')");
  }
  
  const headersStr = formatJson(headers, 2);
  
  if (request.body) {
    code += `payload = ${formatJson(request.body)}\n\n`;
    code += `response = requests.${request.method.toLowerCase()}("${url}", json=payload, headers=${headersStr})\n`;
  } else {
    code += `response = requests.${request.method.toLowerCase()}("${url}", headers=${headersStr})\n`;
  }
  
  code += "data = response.json()";
  
  return code;
}

export function generateGo(request: APIRequest): string {
  const baseUrl = getBaseUrl(request.authType);
  const url = `${baseUrl}${request.path}${buildQueryString(request.query)}`;
  const authHeader = getAuthHeader(request.authType);
  
  let code = `package main\n\n`;
  code += `import (\n`;
  code += `\t"bytes"\n`;
  code += `\t"encoding/json"\n`;
  code += `\t"fmt"\n`;
  code += `\t"net/http"\n`;
  code += `\t"os"\n`;
  code += `)\n\n`;
  
  code += `func main() {\n`;
  code += `\turl := "${url}"\n\n`;
  
  if (request.body) {
    code += `\tpayload := ${formatJson(request.body).replace(/\n/g, "\n\t")}\n`;
    code += `\tjsonData, _ := json.Marshal(payload)\n\n`;
  }
  
  code += `\treq, _ := http.NewRequest("${request.method.toUpperCase()}", url, `;
  if (request.body) {
    code += `bytes.NewBuffer(jsonData)`;
  } else {
    code += `nil`;
  }
  code += `)\n`;
  
  code += `\treq.Header.Set("Content-Type", "application/json")\n`;
  
  if (authHeader) {
    const [key, value] = authHeader.split(": ");
    const envVar = value.includes("ADMIN") ? "VEXA_ADMIN_API_KEY" : "VEXA_API_KEY";
    code += `\treq.Header.Set("${key}", os.Getenv("${envVar}"))\n`;
  }
  
  code += `\n\tclient := &http.Client{}\n`;
  code += `\tresp, err := client.Do(req)\n`;
  code += `\tif err != nil {\n`;
  code += `\t\tpanic(err)\n`;
  code += `\t}\n`;
  code += `\tdefer resp.Body.Close()\n\n`;
  code += `\tvar data map[string]interface{}\n`;
  code += `\tjson.NewDecoder(resp.Body).Decode(&data)\n`;
  code += `}`;
  
  return code;
}

export function generateRuby(request: APIRequest): string {
  const baseUrl = getBaseUrl(request.authType);
  const url = `${baseUrl}${request.path}${buildQueryString(request.query)}`;
  const authHeader = getAuthHeader(request.authType);
  
  let code = "require 'net/http'\nrequire 'json'\nrequire 'uri'\n\n";
  
  code += `uri = URI("${url}")\n`;
  
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...request.headers,
  };
  
  if (authHeader) {
    const [key, value] = authHeader.split(": ");
    const envVar = value.includes("ADMIN") ? "ENV['VEXA_ADMIN_API_KEY']" : "ENV['VEXA_API_KEY']";
    headers[key] = envVar;
  }
  
  code += `headers = ${formatJson(headers).replace(/"/g, "'")}\n\n`;
  
  if (request.body) {
    code += `body = ${formatJson(request.body).replace(/"/g, "'")}\n\n`;
  }
  
  code += `http = Net::HTTP.new(uri.host, uri.port)\n`;
  code += `http.use_ssl = true if uri.scheme == 'https'\n\n`;
  
  code += `request = Net::HTTP::${request.method.charAt(0).toUpperCase() + request.method.slice(1).toLowerCase()}.new(uri)\n`;
  code += `headers.each { |k, v| request[k] = v }\n`;
  
  if (request.body) {
    code += `request.body = body.to_json\n`;
  }
  
  code += `\nresponse = http.request(request)\n`;
  code += `data = JSON.parse(response.body)`;
  
  return code;
}

export function generateJava(request: APIRequest): string {
  const baseUrl = getBaseUrl(request.authType);
  const url = `${baseUrl}${request.path}${buildQueryString(request.query)}`;
  const authHeader = getAuthHeader(request.authType);
  
  let code = `import java.net.http.HttpClient;\n`;
  code += `import java.net.http.HttpRequest;\n`;
  code += `import java.net.http.HttpResponse;\n`;
  code += `import java.net.URI;\n`;
  code += `import java.net.http.HttpRequest.BodyPublishers;\n`;
  code += `import java.net.http.HttpRequest.BodyHandlers;\n`;
  code += `import com.google.gson.Gson;\n\n`;
  
  code += `public class VexaAPI {\n`;
  code += `\tpublic static void main(String[] args) {\n`;
  code += `\t\tString url = "${url}";\n`;
  code += `\t\tHttpClient client = HttpClient.newHttpClient();\n\n`;
  
  if (request.body) {
    code += `\t\tString jsonBody = new Gson().toJson(${formatJson(request.body).replace(/\n/g, "\n\t\t")});\n\n`;
  }
  
  code += `\t\tHttpRequest.Builder requestBuilder = HttpRequest.newBuilder()\n`;
  code += `\t\t\t.uri(URI.create(url))\n`;
  code += `\t\t\t.header("Content-Type", "application/json")\n`;
  
  if (authHeader) {
    const [key, value] = authHeader.split(": ");
    const envVar = value.includes("ADMIN") ? "System.getenv(\"VEXA_ADMIN_API_KEY\")" : "System.getenv(\"VEXA_API_KEY\")";
    code += `\t\t\t.header("${key}", ${envVar})\n`;
  }
  
  code += `\t\t\t.${request.method.toUpperCase()}(`;
  if (request.body) {
    code += `BodyPublishers.ofString(jsonBody)`;
  } else {
    code += `BodyPublishers.noBody()`;
  }
  code += `);\n\n`;
  
  code += `\t\tHttpRequest request = requestBuilder.build();\n\n`;
  code += `\t\ttry {\n`;
  code += `\t\t\tHttpResponse<String> response = client.send(request, BodyHandlers.ofString());\n`;
  code += `\t\t\tString data = response.body();\n`;
  code += `\t\t} catch (Exception e) {\n`;
  code += `\t\t\te.printStackTrace();\n`;
  code += `\t\t}\n`;
  code += `\t}\n`;
  code += `}`;
  
  return code;
}

export function generateCSharp(request: APIRequest): string {
  const baseUrl = getBaseUrl(request.authType);
  const url = `${baseUrl}${request.path}${buildQueryString(request.query)}`;
  const authHeader = getAuthHeader(request.authType);
  
  let code = `using System;\n`;
  code += `using System.Net.Http;\n`;
  code += `using System.Text;\n`;
  code += `using System.Text.Json;\n`;
  code += `using System.Threading.Tasks;\n\n`;
  
  code += `class Program\n`;
  code += `{\n`;
  code += `\tstatic async Task Main(string[] args)\n`;
  code += `\t{\n`;
  code += `\t\tvar client = new HttpClient();\n`;
  code += `\t\tvar url = "${url}";\n\n`;
  
  code += `\t\tvar request = new HttpRequestMessage(HttpMethod.${request.method.charAt(0).toUpperCase() + request.method.slice(1).toLowerCase()}, url);\n`;
  code += `\t\trequest.Headers.Add("Content-Type", "application/json");\n`;
  
  if (authHeader) {
    const [key, value] = authHeader.split(": ");
    const envVar = value.includes("ADMIN") ? "Environment.GetEnvironmentVariable(\"VEXA_ADMIN_API_KEY\")" : "Environment.GetEnvironmentVariable(\"VEXA_API_KEY\")";
    code += `\t\trequest.Headers.Add("${key}", ${envVar});\n`;
  }
  
  if (request.body) {
    code += `\t\tvar json = JsonSerializer.Serialize(${formatJson(request.body).replace(/\n/g, "\n\t\t")});\n`;
    code += `\t\trequest.Content = new StringContent(json, Encoding.UTF8, "application/json");\n`;
  }
  
  code += `\n\t\tvar response = await client.SendAsync(request);\n`;
  code += `\t\tvar data = await response.Content.ReadAsStringAsync();\n`;
  code += `\t}\n`;
  code += `}`;
  
  return code;
}

export function generateCodeExamples(request: APIRequest): CodeExample[] {
  return [
    {
      language: "bash",
      label: "cURL",
      code: generateCurl(request),
    },
    {
      language: "javascript",
      label: "JavaScript",
      code: generateJavaScript(request),
    },
    {
      language: "python",
      label: "Python",
      code: generatePython(request),
    },
    {
      language: "go",
      label: "Go",
      code: generateGo(request),
    },
    {
      language: "ruby",
      label: "Ruby",
      code: generateRuby(request),
    },
    {
      language: "java",
      label: "Java",
      code: generateJava(request),
    },
    {
      language: "csharp",
      label: "C#",
      code: generateCSharp(request),
    },
  ];
}

