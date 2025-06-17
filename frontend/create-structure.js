const fs = require("fs");
const path = require("path");

const structure = {
  "src": {
    "components": [
      "DataCard.tsx",
      "Dashboard.tsx",
      "LatestReadingsDisplay.tsx",
      "LineChartComponent.tsx",
      "LoadingSpinner.tsx",
      "MeterSelector.tsx",
      "MetricsDisplay.tsx"
    ],
    "services": ["api.ts"],
    "": ["App.tsx", "index.tsx", "types.ts"]
  },
  "": ["index.html", "metadata.json"]
};

function createStructure(base, obj) {
  for (const key in obj) {
    const item = obj[key];
    const folderPath = key === "" ? base : path.join(base, key);

    if (!fs.existsSync(folderPath)) {
      fs.mkdirSync(folderPath, { recursive: true });
      console.log(`📁 Created folder: ${folderPath}`);
    }

    if (Array.isArray(item)) {
      // Direct file list
      for (const file of item) {
        const filePath = path.join(folderPath, file);
        fs.writeFileSync(filePath, "");
        console.log(`📄 Created file: ${filePath}`);
      }
    } else if (typeof item === "object") {
      // Nested structure
      createStructure(folderPath, item);
    }
  }
}

createStructure(process.cwd(), structure);
