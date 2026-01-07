# Initialize conda for Cursor/VS Code terminal
# This script ensures conda is available and environment variables are set

# Load user and machine PATH environment variables
$env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User')

# Find conda installation
$condaPaths = @(
    "$env:USERPROFILE\anaconda3\Scripts\conda.exe",
    "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
    "$env:LOCALAPPDATA\Programs\Anaconda3\Scripts\conda.exe",
    "$env:LOCALAPPDATA\Programs\Miniconda3\Scripts\conda.exe",
    "C:\ProgramData\anaconda3\Scripts\conda.exe",
    "C:\ProgramData\miniconda3\Scripts\conda.exe"
)

$condaExe = $null
foreach ($path in $condaPaths) {
    if (Test-Path $path) {
        $condaExe = $path
        break
    }
}

# If conda is found, initialize it
if ($condaExe) {
    $condaBase = Split-Path (Split-Path $condaExe -Parent) -Parent
    & "$condaBase\Scripts\conda.exe" init powershell --quiet | Out-Null
    
    # Activate base environment
    if (Test-Path "$condaBase\Scripts\activate.ps1") {
        & "$condaBase\Scripts\activate.ps1" base
    }
} else {
    # Try to use conda if it's already in PATH (from system initialization)
    try {
        $condaInfo = conda info --json 2>$null
        if ($condaInfo) {
            conda activate base 2>$null
        }
    } catch {
        Write-Host "Conda not found. Please ensure conda is installed and in your PATH." -ForegroundColor Yellow
    }
}


