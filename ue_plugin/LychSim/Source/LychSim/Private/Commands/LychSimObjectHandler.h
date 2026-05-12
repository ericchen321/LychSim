#pragma once

#include "CommandDispatcher.h"
#include "CommandHandler.h"

class FLychSimObjectHandler : public FCommandHandler
{
public:
	void RegisterCommands();

private:
	FExecStatus ListObjects(const TArray<FString>& Args);

	FExecStatus GetObjectLocation(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
	FExecStatus GetObjectRotation(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
	FExecStatus SetObjectLocation(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
	FExecStatus SetObjectRotation(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
	FExecStatus UpdateObject(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
	FExecStatus GetObjectAABB(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
	FExecStatus GetObjectOBB(const TArray<FString>& Args);
	FExecStatus GetObjectAnnotationColor(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
	FExecStatus GetObjectAnnotations(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);

	FExecStatus GetObjectIDFromSelection(const TArray<FString>& Args);

	FExecStatus AddObject(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
	FExecStatus GetMeshExtent(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
	FExecStatus ExportMeshes(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
	FExecStatus DestroyObject(const TArray<FString>& Args);

	FExecStatus SetObjectMaterial(const TArray<FString>& Args);

	FExecStatus AdjustLight(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags);
};
