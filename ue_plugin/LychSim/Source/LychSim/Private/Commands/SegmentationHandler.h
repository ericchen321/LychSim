//file added for the part segmentation
#pragma once
#include "CommandDispatcher.h"
#include "CommandHandler.h"

class FSegmentationHandler : public FCommandHandler
{
public:
    FSegmentationHandler() : CurrentMode(TEXT("part")) {}
    virtual void RegisterCommands() override;

private:
    FString CurrentMode;

    FExecStatus SetMode(const TArray<FString>& Args);
    FExecStatus GetMode(const TArray<FString>& Args);

    void ReannotateWorld(const FString& Mode);
};

