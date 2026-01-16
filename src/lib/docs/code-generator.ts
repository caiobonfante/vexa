export interface APIRequest {
  method: string;
  path: string;
  authType: "user" | "admin" | "none";
  headers?: Record<string, string>;
  query?: Record<string, string>;
  body?: unknown;
}

export interface CodeExample {
  language: string;
  label: string;
  code: string;
}

function buildUrl(path: string, query?: Record<string, string>): string {
  const baseUrl = "https://api.vexa.ai";
  let url = `${baseUrl}${path}`;
  
  if (query && Object.keys(query).length > 0) {
    const params = new URLSearchParams();
    Object.entries(query).forEach(([key, value]) => {
      if (value) params.append(key, value);
    });
    url += `?${params.toString()}`;
  }
  
  return url;
}

function generateJavaScriptExample(request: APIRequest): string {
  const url = buildUrl(request.path, request.query);
  const headers: Record<string, string> = {
    ...request.headers,
  };

  if (request.authType === "user") {
    headers["X-API-Key"] = "YOUR_API_KEY";
  } else if (request.authType === "admin") {
    headers["X-Admin-API-Key"] = "YOUR_ADMIN_API_KEY";
  }

  let code = `const response = await fetch('${url}', {\n`;
  code += `  method: '${request.method}',\n`;
  
  if (Object.keys(headers).length > 0) {
    code += `  headers: {\n`;
    Object.entries(headers).forEach(([key, value]) => {
      code += `    '${key}': '${value}',\n`;
    });
    code += `  },\n`;
  }
  
  if (request.body && (request.method === "POST" || request.method === "PUT" || request.method === "PATCH")) {
    code += `  body: JSON.stringify(${JSON.stringify(request.body, null, 2)}),\n`;
  }
  
  code += `});\n\n`;
  code += `const data = await response.json();\n`;
  code += `console.log(data);`;

  return code;
}

function generatePythonExample(request: APIRequest): string {
  const url = buildUrl(request.path, request.query);
  const headers: Record<string, string> = {
    ...request.headers,
  };

  if (request.authType === "user") {
    headers["X-API-Key"] = "YOUR_API_KEY";
  } else if (request.authType === "admin") {
    headers["X-Admin-API-Key"] = "YOUR_ADMIN_API_KEY";
  }

  let code = `import requests\n\n`;
  code += `url = '${url}'\n`;
  code += `headers = {\n`;
  Object.entries(headers).forEach(([key, value]) => {
    code += `    '${key}': '${value}',\n`;
  });
  code += `}\n\n`;

  if (request.body && (request.method === "POST" || request.method === "PUT" || request.method === "PATCH")) {
    code += `data = ${JSON.stringify(request.body, null, 2)}\n\n`;
    code += `response = requests.${request.method.toLowerCase()}(url, headers=headers, json=data)\n`;
  } else {
    code += `response = requests.${request.method.toLowerCase()}(url, headers=headers)\n`;
  }
  
  code += `print(response.json())`;

  return code;
}

function generateCurlExample(request: APIRequest): string {
  const url = buildUrl(request.path, request.query);
  const headers: Record<string, string> = {
    ...request.headers,
  };

  if (request.authType === "user") {
    headers["X-API-Key"] = "YOUR_API_KEY";
  } else if (request.authType === "admin") {
    headers["X-Admin-API-Key"] = "YOUR_ADMIN_API_KEY";
  }

  let code = `curl -X ${request.method} '${url}' \\\n`;
  
  Object.entries(headers).forEach(([key, value]) => {
    code += `  -H '${key}: ${value}' \\\n`;
  });

  if (request.body && (request.method === "POST" || request.method === "PUT" || request.method === "PATCH")) {
    code += `  -d '${JSON.stringify(request.body)}'`;
  } else {
    // Remove trailing backslash
    code = code.trimEnd().replace(/\\$/, "");
  }

  return code;
}

function generateGoExample(request: APIRequest): string {
  const url = buildUrl(request.path, request.query);

  let code = `package main\n\n`;
  code += `import (\n`;
  code += `    "bytes"\n`;
  code += `    "encoding/json"\n`;
  code += `    "fmt"\n`;
  code += `    "net/http"\n`;
  code += `)\n\n`;
  code += `func main() {\n`;
  code += `    url := "${url}"\n\n`;
  
  if (request.body && (request.method === "POST" || request.method === "PUT" || request.method === "PATCH")) {
    code += `    data := map[string]interface{}{\n`;
    if (typeof request.body === "object" && request.body !== null) {
      Object.entries(request.body as Record<string, unknown>).forEach(([key, value]) => {
        const goValue = typeof value === "string" ? `"${value}"` : JSON.stringify(value);
        code += `        "${key}": ${goValue},\n`;
      });
    }
    code += `    }\n`;
    code += `    jsonData, _ := json.Marshal(data)\n`;
    code += `    req, _ := http.NewRequest("${request.method}", url, bytes.NewBuffer(jsonData))\n`;
  } else {
    code += `    req, _ := http.NewRequest("${request.method}", url, nil)\n`;
  }
  
  code += `    req.Header.Set("Content-Type", "application/json")\n`;
  if (request.authType === "user") {
    code += `    req.Header.Set("X-API-Key", "YOUR_API_KEY")\n`;
  } else if (request.authType === "admin") {
    code += `    req.Header.Set("X-Admin-API-Key", "YOUR_ADMIN_API_KEY")\n`;
  }
  
  code += `\n`;
  code += `    client := &http.Client{}\n`;
  code += `    resp, _ := client.Do(req)\n`;
  code += `    defer resp.Body.Close()\n\n`;
  code += `    var result map[string]interface{}\n`;
  code += `    json.NewDecoder(resp.Body).Decode(&result)\n`;
  code += `    fmt.Println(result)\n`;
  code += `}`;

  return code;
}

function generateRubyExample(request: APIRequest): string {
  const url = buildUrl(request.path, request.query);
  const methodMap: Record<string, string> = {
    GET: "Get",
    POST: "Post",
    PUT: "Put",
    PATCH: "Patch",
    DELETE: "Delete",
  };
  const methodClass = methodMap[request.method.toUpperCase()] || "Get";

  let code = `require 'net/http'\n`;
  code += `require 'json'\n\n`;
  code += `uri = URI('${url}')\n\n`;
  
  if (request.method === "GET") {
    code += `response = Net::HTTP.get_response(uri)\n`;
  } else {
    code += `http = Net::HTTP.new(uri.host, uri.port)\n`;
    code += `http.use_ssl = true if uri.scheme == 'https'\n\n`;
    code += `request = Net::HTTP::${methodClass}.new(uri)\n`;
    code += `request['Content-Type'] = 'application/json'\n`;
    
    if (request.authType === "user") {
      code += `request['X-API-Key'] = 'YOUR_API_KEY'\n`;
    } else if (request.authType === "admin") {
      code += `request['X-Admin-API-Key'] = 'YOUR_ADMIN_API_KEY'\n`;
    }
    
    if (request.body && (request.method === "POST" || request.method === "PUT" || request.method === "PATCH")) {
      code += `request.body = ${JSON.stringify(request.body)}.to_json\n`;
    }
    
    code += `\nresponse = http.request(request)\n`;
  }
  
  code += `puts JSON.parse(response.body)`;

  return code;
}

function generatePHPExample(request: APIRequest): string {
  const url = buildUrl(request.path, request.query);
  const headers: Record<string, string> = {
    ...request.headers,
  };

  if (request.authType === "user") {
    headers["X-API-Key"] = "YOUR_API_KEY";
  } else if (request.authType === "admin") {
    headers["X-Admin-API-Key"] = "YOUR_ADMIN_API_KEY";
  }

  let code = `<?php\n\n`;
  code += `$url = '${url}';\n`;
  code += `$headers = [\n`;
  Object.entries(headers).forEach(([key, value]) => {
    code += `    '${key}: ${value}',\n`;
  });
  code += `];\n\n`;

  code += `$ch = curl_init($url);\n`;
  code += `curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);\n`;
  code += `curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);\n`;
  code += `curl_setopt($ch, CURLOPT_CUSTOMREQUEST, '${request.method}');\n`;

  if (request.body && (request.method === "POST" || request.method === "PUT" || request.method === "PATCH")) {
    code += `curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode(${JSON.stringify(request.body)}));\n`;
  }

  code += `\n$response = curl_exec($ch);\n`;
  code += `curl_close($ch);\n\n`;
  code += `$data = json_decode($response, true);\n`;
  code += `print_r($data);`;

  return code;
}

export function generateCodeExamples(request: APIRequest): CodeExample[] {
  return [
    {
      language: "javascript",
      label: "JavaScript",
      code: generateJavaScriptExample(request),
    },
    {
      language: "python",
      label: "Python",
      code: generatePythonExample(request),
    },
    {
      language: "curl",
      label: "cURL",
      code: generateCurlExample(request),
    },
    {
      language: "go",
      label: "Go",
      code: generateGoExample(request),
    },
    {
      language: "ruby",
      label: "Ruby",
      code: generateRubyExample(request),
    },
    {
      language: "php",
      label: "PHP",
      code: generatePHPExample(request),
    },
  ];
}
