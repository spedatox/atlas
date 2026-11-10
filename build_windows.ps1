param([string]$Python = 'python')

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Get-VerifiedDownload($Url, $Destination, $Sha256) {
    if ((Test-Path -LiteralPath $Destination) -and (Get-FileHash -LiteralPath $Destination).Hash -eq $Sha256) {
        return
    }
    Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Destination
    if ((Get-FileHash -LiteralPath $Destination).Hash -ne $Sha256) {
        throw "Checksum mismatch for $Destination"
    }
}

Push-Location -LiteralPath $PSScriptRoot
try {
    & $Python -c "import platform, struct; assert platform.system() == 'Windows' and platform.machine() == 'AMD64' and struct.calcsize('P') == 8, 'Use x64 Windows Python'"
    if ($LASTEXITCODE -ne 0) { throw 'A Windows x64 Python installation is required.' }

    & $Python -m pip install 'PySide6-Essentials==6.12.0' 'pyinstaller==6.20.0'
    if ($LASTEXITCODE -ne 0) { throw 'Unable to install Windows build dependencies.' }

    $toolsDir = Join-Path $PSScriptRoot 'build\windows-tools'
    $stage = Join-Path $PSScriptRoot ('build\package-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $toolsDir, $stage -Force | Out-Null

    $compilerDir = Join-Path $toolsDir 'Inno-6.7.4'
    $compiler = Join-Path $compilerDir 'ISCC.exe'
    if (-not (Test-Path -LiteralPath $compiler)) {
        $compilerSetup = Join-Path $toolsDir 'innosetup-6.7.4.exe'
        Get-VerifiedDownload 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_4/innosetup-6.7.4.exe' `
            $compilerSetup 'a549929319f9120716677c685535ca4671e4b937b5fdc87e2585f32d8eb30e8c'
        $installCompiler = Start-Process -FilePath $compilerSetup -WindowStyle Hidden -Wait -PassThru -ArgumentList @(
            '/PORTABLE=1', '/CURRENTUSER', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS', "/DIR=`"$compilerDir`""
        )
        if ($installCompiler.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $compiler)) {
            throw 'Inno Setup compiler installation failed.'
        }
    }

    $plink = Join-Path $toolsDir 'plink.exe'
    Get-VerifiedDownload 'https://the.earth.li/~sgtatham/putty/0.85/w64/plink.exe' `
        $plink '969f36879d5716aa1a9811f43a6a6510e8f08372dbeb9695b810b9c776f39c75'
    $puttySource = Join-Path $toolsDir 'putty-0.85.tar.gz'
    Get-VerifiedDownload 'https://the.earth.li/~sgtatham/putty/0.85/putty-0.85.tar.gz' `
        $puttySource '13fd4db2936d03b73812a7bcc2a658e4dd29cc776a56c3670a7fc6f1a0ee8af8'
    & tar.exe -xf $puttySource -C $stage 'putty-0.85/LICENCE'
    if ($LASTEXITCODE -ne 0) { throw 'Unable to extract the PuTTY license.' }

    $distDir = Join-Path $stage 'dist'
    & $Python -m PyInstaller --noconfirm --workpath (Join-Path $stage 'work') --distpath $distDir atlas.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

    $package = Join-Path $distDir 'ATLAS'
    Copy-Item -LiteralPath $plink -Destination $package
    $licenses = Join-Path $package 'licenses'
    New-Item -ItemType Directory -Path $licenses | Out-Null
    Copy-Item -LiteralPath (Join-Path $stage 'putty-0.85\LICENCE') -Destination (Join-Path $licenses 'PuTTY-LICENCE.txt')

    $sitePackages = & $Python -c "import sysconfig; print(sysconfig.get_path('purelib'))"
    if ($LASTEXITCODE -ne 0) { throw 'Unable to locate installed package licenses.' }
    foreach ($distribution in (Get-ChildItem -LiteralPath $sitePackages -Directory -Filter '*.dist-info')) {
        if ($distribution.Name -match '^(pyside6_essentials|shiboken6|pyinstaller)-') {
            $wheelLicenses = Join-Path $distribution.FullName 'licenses'
            if (Test-Path -LiteralPath $wheelLicenses) {
                Copy-Item -LiteralPath $wheelLicenses -Destination (Join-Path $licenses $distribution.BaseName) -Recurse
            }
        }
    }

    & $compiler "/DPackageDir=$package" installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'ATLAS installer compilation failed.' }
    Write-Host (Join-Path $PSScriptRoot 'dist\ATLAS-Setup-x64.exe')
}
finally {
    Pop-Location
}
