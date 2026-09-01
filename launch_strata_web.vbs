' Strata Console (WEB SHELL) - silent launcher.
'
' Same interpreter rule as launch_strata.vbs, for the same reason:
' the web shell needs sounddevice and faster_whisper too, and the
' Store Python does not have them (FB-002). This picks the same
' voice-capable interpreter, then runs strata_web.py instead.
'
' Picks the interpreter that can run the WHOLE app, voice included.
'
' History, so this is not "fixed" back into a defect: the launcher used
' to hunt down the Store Python under C:\Program Files\WindowsApps and
' launch that, because the bare "pythonw" alias does not resolve when a
' script starts it. That solved the alias problem and quietly created a
' worse one -- sounddevice and faster_whisper are installed in the
' ordinary per-user Python, not the Store one, so the microphone button
' died on import while the bench check (run with "py -3", a different
' interpreter again) reported the voice path healthy.
'
' The rule now: prefer a real per-user or machine install, and among the
' candidates prefer one that actually carries the voice packages. A real
' pythonw.exe is a full path, so the alias problem never returns either.
' The same rule is unit-tested in strata_tools/interpreter.py.

Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
q = Chr(34)

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
script = appDir & "\strata_web.py"

' ---- Collect candidate pythonw.exe paths, in preference order ---------
Dim cand(20), nCand
nCand = 0

localApp = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%")
AddPythonsUnder localApp & "\Programs\Python"
AddPythonsUnder sh.ExpandEnvironmentStrings("%ProgramFiles%")
AddPythonsUnder "C:\"
AddStorePythons

' ---- Prefer a candidate that carries the voice packages ---------------
pyw = ""
For i = 0 To nCand - 1
    If HasVoiceDeps(cand(i)) Then
        pyw = cand(i)
        Exit For
    End If
Next

' Nothing voice-capable: fall back to the first that can run the app at
' all. The console itself then reports which interpreter it is on and
' the exact pip line for it, so this never reads as a dead microphone.
If pyw = "" And nCand > 0 Then pyw = cand(0)

' "/which" reports the choice and launches nothing -- so the owner (and
' the bench) can see which interpreter a double-click would really use.
If WScript.Arguments.Count > 0 Then
    If LCase(WScript.Arguments(0)) = "/which" Then
        If pyw = "" Then
            WScript.Echo "pythonw (alias fallback)"
        Else
            WScript.Echo pyw
        End If
        WScript.Quit 0
    End If
End If

If pyw <> "" Then
    sh.Run "cmd /c " & q & q & pyw & q & " " & q & script & q & q, 0, False
Else
    sh.Run "cmd /c pythonw " & q & script & q, 0, False
End If

' ---- helpers ----------------------------------------------------------

' Add <root>\Python3*\pythonw.exe for every matching subfolder.
Sub AddPythonsUnder(root)
    If Not fso.FolderExists(root) Then Exit Sub
    On Error Resume Next
    For Each f In fso.GetFolder(root).SubFolders
        If LCase(Left(f.Name, 7)) = "python3" Then
            AddCandidate f.Path & "\pythonw.exe"
        End If
    Next
    On Error GoTo 0
End Sub

' Add the Store Python under the protected WindowsApps folder (last
' resort: pip installs there land in a separate LocalCache tree, which
' is how the voice packages went missing in the first place).
Sub AddStorePythons()
    root = "C:\Program Files\WindowsApps"
    If Not fso.FolderExists(root) Then Exit Sub
    On Error Resume Next
    For Each f In fso.GetFolder(root).SubFolders
        If InStr(f.Name, "PythonSoftwareFoundation.Python.3.") > 0 Then
            For Each exe In f.Files
                If LCase(Left(exe.Name, 7)) = "pythonw" And _
                   LCase(fso.GetExtensionName(exe.Name)) = "exe" Then
                    AddCandidate exe.Path
                End If
            Next
        End If
    Next
    On Error GoTo 0
End Sub

Sub AddCandidate(path)
    If nCand > UBound(cand) Then Exit Sub
    If Not fso.FileExists(path) Then Exit Sub
    For j = 0 To nCand - 1
        If LCase(cand(j)) = LCase(path) Then Exit Sub
    Next
    cand(nCand) = path
    nCand = nCand + 1
End Sub

' Mirror of strata_tools.interpreter.has_voice_deps: a dependency counts
' as present as either <dep>.py or <dep>\ inside Lib\site-packages.
Function HasVoiceDeps(pywPath)
    sp = fso.GetParentFolderName(pywPath) & "\Lib\site-packages"
    HasVoiceDeps = DepPresent(sp, "sounddevice") And _
                   DepPresent(sp, "faster_whisper")
End Function

Function DepPresent(sitePkgs, dep)
    DepPresent = fso.FileExists(sitePkgs & "\" & dep & ".py") Or _
                 fso.FolderExists(sitePkgs & "\" & dep)
End Function
