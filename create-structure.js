const fs = require('fs');
const path = require('path');

// Define folder structure
const structure = [
  'digital-twin-frontend/public',
  'digital-twin-frontend/src/components/icons',
  'digital-twin-frontend/src/services',
];

// Define files to create with optional sample content
const files = {
  'digital-twin-frontend/src/components/icons/RefreshIcon.tsx': '',
  'digital-twin-frontend/src/components/Dashboard.tsx': '',
  'digital-twin-frontend/src/components/DemandChart.tsx': '',
  'digital-twin-frontend/src/components/ErrorMessage.tsx': '',
  'digital-twin-frontend/src/components/MeterSelector.tsx': '',
  'digital-twin-frontend/src/components/MetricsCard.tsx': '',
  'digital-twin-frontend/src/components/ReadingsTable.tsx': '',
  'digital-twin-frontend/src/components/Spinner.tsx': '',
  'digital-twin-frontend/src/services/apiService.ts': '',
  'digital-twin-frontend/src/App.tsx': '',
  'digital-twin-frontend/src/constants.ts': '',
  'digital-twin-frontend/src/index.tsx': '',
  'digital-twin-frontend/src/types.ts': '',
  'digital-twin-frontend/index.html': '',
  'digital-twin-frontend/metadata.json': '{}',
  'digital-twin-frontend/package.json': '{}',
  'digital-twin-frontend/tsconfig.json': '{}',
  'digital-twin-frontend/tsconfig.node.json': '{}',
  'digital-twin-frontend/vite.config.ts': '',
};

// Create folders
structure.forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
    console.log(`📁 Created folder: ${dir}`);
  }
});

// Create files
Object.entries(files).forEach(([filePath, content]) => {
  if (!fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, content);
    console.log(`📄 Created file: ${filePath}`);
  }
});
