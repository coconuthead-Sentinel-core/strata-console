' Strata Console — silent launcher (no console window at all)
' Launches the real pythonw binary by full path (bypasses the flaky Store alias),
' inside a hidden cmd so nothing visible ever appears.
Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
q = Chr(34)

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
script = appDir & "\strata_console.py"

' Find the real pythonw3.x.exe under the protected WindowsApps store folder.
pyw = ""
root = "C:\Program Files\WindowsApps"
If fso.FolderExists(root) Then
    On Error Resume Next
    For Each f In fso.GetFolder(root).SubFolders
        If InStr(f.Name, "PythonSoftwareFoundation.Python.3.") > 0 Then
            For Each exe In f.Files
                If LCase(Left(exe.Name, 7)) = "pythonw" And LCase(fso.GetExtensionName(exe.Name)) = "exe" Then
                    pyw = exe.Path
                End If
            Next
        End If
    Next
    On Error GoTo 0
End If

If pyw <> "" Then
    sh.Run "cmd /c " & q & q & pyw & q & " " & q & script & q & q, 0, False
Else
    ' Fallback: the "pythonw" alias (resolves on a normal desktop double-click)
    sh.Run "cmd /c pythonw " & q & script & q, 0, False
End If
