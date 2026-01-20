$bytes = [System.IO.File]::ReadAllBytes('C:\Users\willi\image_gen_deploy\test_stream.bin')
Write-Host "File size: $($bytes.Length) bytes"
Write-Host ""
Write-Host "First 200 bytes as hex:"
$hex = ($bytes[0..199] | ForEach-Object { '{0:X2}' -f $_ }) -join ' '
Write-Host $hex
Write-Host ""
Write-Host "As ASCII text:"
[System.Text.Encoding]::ASCII.GetString($bytes[0..199])
