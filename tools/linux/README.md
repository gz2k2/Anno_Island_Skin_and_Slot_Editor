# Patched RdaConsole for Linux

`RdaConsole-linux-x64.tar.gz` (or a plain `RdaConsole` binary) is picked up by the
release workflow and shipped inside the Linux release archive.

It is upstream [anno-mods/RdaConsole](https://github.com/anno-mods/RdaConsole), built for
`linux-x64` (self-contained, single file) with a patched `lib/RDAExplorer.dll`:
the string literal `"\"` was changed to `"/"` (see `.github/scripts/patch_rdaexplorer.py`),
because the original library converts archive paths to Windows paths and crashes on Linux
in `Directory.CreateDirectory("")`.

## Rebuild

```bash
python3 .github/scripts/patch_rdaexplorer.py RdaConsole/lib/RDAExplorer.dll
dotnet publish RdaConsole/RdaConsole.csproj -c Release -r linux-x64 --self-contained true \
  -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o out
tar -C out -czf RdaConsole-linux-x64.tar.gz RdaConsole
```

Put the resulting archive here (`tools/linux/`). Do not use this binary on Windows.
