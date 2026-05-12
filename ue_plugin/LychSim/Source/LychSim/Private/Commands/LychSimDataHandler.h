#pragma once

#include "CommandDispatcher.h"
#include "CommandHandler.h"

class FLychSimDataHandler : public FCommandHandler
{
public:
	void RegisterCommands();

private:
	FExecStatus CollectInfo(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);

	FExecStatus LSDrawDebugLine(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
	FExecStatus LSDrawDebugLinePts(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
	FExecStatus LSClearDebugLines(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);

	FExecStatus LSPause(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
	FExecStatus LSUnPause(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
};
