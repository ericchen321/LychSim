#include "LychSimUtilsHandler.h"
#include "Runtime/Engine/Classes/Engine/World.h"
#include "Runtime/Projects/Public/Interfaces/IPluginManager.h"

#include "UnrealcvServer.h"
#include "UnrealcvShim.h"
#include "UnrealcvStats.h"

void FLychSimUtilsHandler::RegisterCommands()
{
	FDispatcherDelegate Cmd;
	FString Help;

	Cmd = FDispatcherDelegate::CreateRaw(this, &FLychSimUtilsHandler::GetVersion);
	Help = "Get the version of LychSim";
	CommandDispatcher->BindCommand(TEXT("lych version"), Cmd, Help);
}

FExecStatus FLychSimUtilsHandler::GetVersion(const TArray<FString>& Args)
{
	TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin("LychSim");
	if (!Plugin.IsValid())
	{
		return FExecStatus::Error("The plugin is not correctly loaded");
	}
	else
	{
		FString PluginName = Plugin->GetName();
		FPluginDescriptor PluginDescriptor = Plugin->GetDescriptor();
		FString VersionName = PluginDescriptor.VersionName;
		int32 VersionNumber = PluginDescriptor.Version;
		return FExecStatus::OK(VersionName);
	}
}
