#pragma once

#include "CommandDispatcher.h"
#include "CommandHandler.h"

class FLychSimUtilsHandler : public FCommandHandler
{
public:
	void RegisterCommands();
	FExecStatus GetVersion(const TArray<FString>& Args);
};
