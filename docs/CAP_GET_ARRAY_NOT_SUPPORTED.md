# SDK Error Code Reference

## Error -127 (kNkMAIDResult_NotSupported)
This error means the capability or operation is not supported by this camera/module.

## IMPORTANT UPDATE (2025-01-20)
We initially thought `CapGetArray` wasn't supported for `GetLiveViewImage` because it returned -127.

**This was WRONG.** The real issue was we weren't using completion callbacks properly.

With proper async pattern (CompletionProc + IdleLoop), `CapGetArray` works perfectly!

See `HOW_WE_FIXED_SDK_WRITING_ISSUE.md` for the full explanation.