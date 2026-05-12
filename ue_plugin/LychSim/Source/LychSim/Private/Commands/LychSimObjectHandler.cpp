#include "LychSimObjectHandler.h"

#include "LychSimStructuredResponse.h"
#include "Controller/ActorController.h"
#include "Utils/StrFormatter.h"
#include "Utils/UObjectUtils.h"
#include "UnrealcvLog.h"
#include "VisionBPLib.h"
#include "EngineUtils.h"
#include "Engine/DirectionalLight.h"
#include "Components/DirectionalLightComponent.h"
#include "Actor/LychSimBasicActor.h"
#include "Actor/LychSimSkeletalActor.h"
#include "Engine/StaticMesh.h"

#include "Serialization/JsonWriter.h"
#include "Serialization/JsonSerializer.h"

#if WITH_EDITOR
#include "Editor.h"
#include "Editor/UnrealEdEngine.h"
#include "UnrealEdGlobals.h"
#endif

#if WITH_EDITOR
#include "Selection.h"
#endif
#include "GameFramework/Actor.h"

#if WITH_EDITOR
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/AssetData.h"
#include "HAL/FileManager.h"
#include "Misc/App.h"
#include "Misc/Paths.h"
#include "Options/GLTFExportOptions.h"
#include "Exporters/GLTFExporter.h"
#endif

void FLychSimObjectHandler::RegisterCommands()
{
	CommandDispatcher->BindCommand(
		"lych obj list",
		FDispatcherDelegate::CreateRaw(this, &FLychSimObjectHandler::ListObjects),
		"Get a list of all objects."
	);

	CommandDispatcher->BindCommandUE(
		"lych obj get_loc",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimObjectHandler::GetObjectLocation),
		"Get object location [x, y, z]."
	);

	CommandDispatcher->BindCommandUE(
		"lych obj get_rot",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimObjectHandler::GetObjectRotation),
		"Get object rotation [pitch, yaw, roll]."
	);

	CommandDispatcher->BindCommandUE(
		"lych obj set_loc",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimObjectHandler::SetObjectLocation),
		"Set object location [x, y, z]."
	);

	CommandDispatcher->BindCommandUE(
		"lych obj set_rot",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimObjectHandler::SetObjectRotation),
		"Set object rotation [pitch, yaw, roll]."
	);

	CommandDispatcher->BindCommandUE(
		"lych obj update",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimObjectHandler::UpdateObject),
		"Update object properties."
	);

	CommandDispatcher->BindCommandUE(
		"lych obj get_aabb",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimObjectHandler::GetObjectAABB),
		"Get object axis-aligned bounding box [center(3), extent(3)]."
	);

	CommandDispatcher->BindCommand(
		"lych obj get_obb [str]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimObjectHandler::GetObjectOBB),
		"Get object oriented bounding box [center(3), extent(3), rotation_matrix(9)]."
	);

	CommandDispatcher->BindCommandUE(
		"lych obj get_color",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimObjectHandler::GetObjectAnnotationColor),
		"Get object color [r, g, b, a]."
	);

	CommandDispatcher->BindCommandUE(
		"lych obj get_annots",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimObjectHandler::GetObjectAnnotations),
		"Get all object annotations."
	);

	CommandDispatcher->BindCommandUE(
		"lych obj add",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimObjectHandler::AddObject),
		"Add object to the scene."
	);

	CommandDispatcher->BindCommandUE(
		"lych obj get_mesh_extent",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimObjectHandler::GetMeshExtent),
		"Get object mesh extent [x, y, z]."
	);

	CommandDispatcher->BindCommandUE(
		"lych obj export_meshes",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimObjectHandler::ExportMeshes),
		"Export static meshes under a given content path to glTF/glb files."
	);

	CommandDispatcher->BindCommand(
		"lych obj del [str]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimObjectHandler::DestroyObject),
		"Destroy object from the scene."
	);

	CommandDispatcher->BindCommand(
		"lych obj set_mtl [str] [str] [str]",
		FDispatcherDelegate::CreateRaw(this, &FLychSimObjectHandler::SetObjectMaterial),
		"Set object material."
	);

	CommandDispatcher->BindCommand(
		"lych obj list_selected",
		FDispatcherDelegate::CreateRaw(this, &FLychSimObjectHandler::GetObjectIDFromSelection),
		"Get the object ID from the current selection in the editor."
	);

	CommandDispatcher->BindCommandUE(
		"lych obj adjust_light",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimObjectHandler::AdjustLight),
		"Adjust the light properties."
	);
}

AActor* LychSimGetActor(const TArray<FString>& Args)
{
	if (Args.Num() == 0) return nullptr;
	FString ActorId = Args[0];
	AActor* Actor = GetActorById(FUnrealcvServer::Get().GetWorld(), ActorId);
	return Actor;
}

UWorld* GetPIEWorld()
{
	if (GEngine)
	{
		for (const FWorldContext& Context : GEngine->GetWorldContexts())
		{
			if (Context.WorldType == EWorldType::PIE)
			{
				return Context.World();
			}
		}
	}
	return nullptr;
}

bool ExistsActor(UWorld* World, const FString& ActorName)
{
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		if (It->GetName() == ActorName)
		{
			return true;
		}
	}
	return false;
}

FExecStatus FLychSimObjectHandler::ListObjects(const TArray<FString>& Args)
{
	TArray<AActor*> ActorList;
	UVisionBPLib::GetActorList(ActorList);

	FLychSimStructuredResponse R;
	R.BeginOutputs();
	for (AActor* Actor : ActorList)
	{
		R.Writer()->WriteValue(Actor->GetName());
	}
	return R.FinishBatch(ActorList.Num(), ActorList.Num(), FString());
}

FExecStatus FLychSimObjectHandler::GetObjectLocation(
	const TArray<FString>& Pos,
    const TMap<FString,FString>& Kw,
    const TSet<FString>& Flags)
{
	// Build (RequestedId, Actor) pairs so we can report `not_found` against
	// the exact string the caller passed in, even when GetActorById returns
	// nullptr. For the -all flag every actor is real by construction.
	TArray<TPair<FString, AActor*>> Requested;
	if (Flags.Contains("all"))
	{
		TArray<AActor*> ActorList;
		UVisionBPLib::GetActorList(ActorList);
		for (AActor* Actor : ActorList)
		{
			Requested.Emplace(Actor ? Actor->GetName() : FString(), Actor);
		}
	}
	else
	{
		for (const FString& ActorId : Pos)
		{
			AActor* Actor = GetActorById(FUnrealcvServer::Get().GetWorld(), ActorId);
			Requested.Emplace(ActorId, Actor);
		}
	}

	const int32 Total = Requested.Num();
	TArray<FString> MissingIds;
	for (const TPair<FString, AActor*>& Entry : Requested)
	{
		if (!Entry.Value)
		{
			MissingIds.Add(Entry.Key);
		}
	}
	const int32 OkCount = Total - MissingIds.Num();

	FLychSimStructuredResponse R;
	R.BeginOutputs();

	for (const TPair<FString, AActor*>& Entry : Requested)
	{
		const FString& RequestedId = Entry.Key;
		AActor* Actor = Entry.Value;

		R.Writer()->WriteObjectStart();
		R.Writer()->WriteValue(TEXT("object_id"), *RequestedId);

		if (!Actor)
		{
			R.Writer()->WriteValue(TEXT("status"), TEXT("not_found"));
		}
		else
		{
			R.Writer()->WriteValue(TEXT("status"), TEXT("ok"));

			FActorController Controller(Actor);
			FVector Location = Controller.GetLocation();

			R.Writer()->WriteArrayStart(TEXT("location"));
			R.Writer()->WriteValue(Location.X); R.Writer()->WriteValue(Location.Y); R.Writer()->WriteValue(Location.Z);
			R.Writer()->WriteArrayEnd();
		}

		R.Writer()->WriteObjectEnd();
	}

	FString ErrorMsg;
	if (MissingIds.Num() > 0)
	{
		const FString Joined = FString::Join(MissingIds, TEXT(", "));
		ErrorMsg = (OkCount == 0)
			? FString::Printf(TEXT("no objects found: %s"), *Joined)
			: FString::Printf(TEXT("%d of %d objects not found: %s"),
				MissingIds.Num(), Total, *Joined);
	}

	return R.FinishBatch(OkCount, Total, ErrorMsg);
}

FExecStatus FLychSimObjectHandler::ExportMeshes(
	const TArray<FString>& Pos,
    const TMap<FString,FString>& Kw,
    const TSet<FString>& Flags)
{
	FString Out;
	TSharedRef< TJsonWriter<> > Writer = TJsonWriterFactory<>::Create(&Out);
	Writer->WriteObjectStart();

#if WITH_EDITOR
	FString RootPath;
	if (Pos.Num() > 0)
	{
		RootPath = Pos[0];
	}
	else
	{
		RootPath = FString::Printf(TEXT("/Game/%s/Mesh"), *FApp::GetProjectName());
	}
	RootPath = RootPath.TrimStartAndEnd();
	if (RootPath.StartsWith(TEXT("/All/")))
	{
		RootPath = FString(TEXT("/")) + RootPath.RightChop(5);
	}
	if (!RootPath.StartsWith(TEXT("/Game")))
	{
		RootPath.RemoveFromStart(TEXT("/"));
		RootPath = FString(TEXT("/Game/")) + RootPath;
	}

	TArray<FString> SearchPaths;
	SearchPaths.Add(RootPath);

	// Be tolerant of Mesh/mesh naming differences.
	FString AltPath = RootPath;
	int32 SlashIdx;
	if (AltPath.FindLastChar(TEXT('/'), SlashIdx))
	{
		const FString Prefix = AltPath.Left(SlashIdx + 1);
		const FString Suffix = AltPath.Mid(SlashIdx + 1);
		if (Suffix.Equals(TEXT("Mesh")))
		{
			SearchPaths.AddUnique(Prefix + TEXT("mesh"));
		}
		else if (Suffix.Equals(TEXT("mesh")))
		{
			SearchPaths.AddUnique(Prefix + TEXT("Mesh"));
		}
	}

	// Remove duplicates if both Mesh/mesh were added.
	TSet<FString> SearchPathSet(SearchPaths);
	SearchPaths = SearchPathSet.Array();

	const bool bRecursive = !Flags.Contains(TEXT("norecursive"));

	int32 MaxExports = -1;
	if (Kw.Contains(TEXT("max")))
	{
		MaxExports = FCString::Atoi(*Kw[TEXT("max")]);
		if (MaxExports < 0) MaxExports = -1;
	}
	const bool bGlbOnly = Flags.Contains(TEXT("glb_only"));
	const bool bKeepExtras = Flags.Contains(TEXT("keep_extras"));

	FString OutputDir = Kw.Contains(TEXT("out"))
		? Kw[TEXT("out")]
		: FPaths::Combine(FPaths::ProjectDir(), TEXT("Plugins/LychSim/Outputs/Mesh"));
	if (FPaths::IsRelative(OutputDir))
	{
		OutputDir = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), OutputDir));
	}
	else
	{
		OutputDir = FPaths::ConvertRelativePathToFull(OutputDir);
	}
	IFileManager::Get().MakeDirectory(*OutputDir, true);

	FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(FName("AssetRegistry"));
	IAssetRegistry& AssetRegistry = AssetRegistryModule.Get();

	if (!Flags.Contains(TEXT("noscan")))
	{
		UE_LOG(LogLychSim, Display, TEXT("ExportMeshes: scanning paths %s"), *FString::Join(SearchPaths, TEXT(",")));
		AssetRegistry.ScanPathsSynchronous(SearchPaths, /*bForceRescan*/ true);
	}
	else
	{
		UE_LOG(LogLychSim, Display, TEXT("ExportMeshes: skipping scan (noscan flag), using existing registry for %s"), *FString::Join(SearchPaths, TEXT(",")));
	}

	Writer->WriteValue(TEXT("status"), TEXT("ok"));
	Writer->WriteValue(TEXT("output_dir"), OutputDir);
	Writer->WriteArrayStart(TEXT("outputs"));

	int32 NumExported = 0;
	int32 NumSeen = 0;
	UGLTFExportOptions* ExportOptions = NewObject<UGLTFExportOptions>(GetTransientPackage());

	for (const FString& SearchPath : SearchPaths)
	{
		TArray<FAssetData> MeshAssetList;
		AssetRegistry.GetAssetsByPath(FName(*SearchPath), MeshAssetList, bRecursive);

		for (const FAssetData& AssetData : MeshAssetList)
		{
			if (MaxExports >= 0 && NumSeen >= MaxExports)
			{
				break;
			}

			const FTopLevelAssetPath AssetClassPath = AssetData.AssetClassPath;
			if (AssetClassPath != UStaticMesh::StaticClass()->GetClassPathName())
			{
				continue; // Only export static meshes.
			}

			++NumSeen;

			Writer->WriteObjectStart();
			const FString AssetPath = AssetData.ToSoftObjectPath().ToString();
			Writer->WriteValue(TEXT("mesh_path"), AssetPath);

			UStaticMesh* StaticMesh = Cast<UStaticMesh>(AssetData.GetAsset());
			if (!StaticMesh)
			{
				UE_LOG(LogLychSim, Warning, TEXT("ExportMeshes: failed to load %s"), *AssetPath);
				Writer->WriteValue(TEXT("status"), TEXT("load_failed"));
				Writer->WriteObjectEnd();
				continue;
			}

			const FString BaseName = AssetData.AssetName.ToString();
			const FString AssetOutputDir = FPaths::Combine(OutputDir, BaseName);
			IFileManager::Get().MakeDirectory(*AssetOutputDir, true);

			const FString BaseFilePath = FPaths::Combine(AssetOutputDir, BaseName);
			const FString GlbPath = BaseFilePath + TEXT(".glb");
			const FString GltfPath = BaseFilePath + TEXT(".gltf");

			FGLTFExportMessages GlbMessages;
			FGLTFExportMessages GltfMessages;
			const bool bGlbOk = UGLTFExporter::ExportToGLTF(StaticMesh, GlbPath, ExportOptions, {}, GlbMessages);
			bool bGltfOk = true;
			if (!bGlbOnly)
			{
				bGltfOk = UGLTFExporter::ExportToGLTF(StaticMesh, GltfPath, ExportOptions, {}, GltfMessages);
			}

			Writer->WriteValue(TEXT("glb_path"), GlbPath);
			if (!bGlbOnly)
			{
				Writer->WriteValue(TEXT("gltf_path"), GltfPath);
			}

			if (bGlbOk && bGltfOk && GlbMessages.Errors.Num() == 0 && GltfMessages.Errors.Num() == 0)
			{
				Writer->WriteValue(TEXT("status"), TEXT("ok"));
				UE_LOG(LogLychSim, Display, TEXT("ExportMeshes: exported %s -> %s (glb/gltf)"), *AssetPath, *BaseFilePath);
				++NumExported;
			}
			else
			{
				Writer->WriteValue(TEXT("status"), TEXT("export_failed"));
				Writer->WriteArrayStart(TEXT("errors"));
				for (const FString& Error : GlbMessages.Errors)
				{
					Writer->WriteValue(Error);
				}
				for (const FString& Error : GltfMessages.Errors)
				{
					Writer->WriteValue(Error);
				}
				Writer->WriteArrayEnd();
				UE_LOG(LogLychSim, Warning, TEXT("ExportMeshes: failed %s"), *AssetPath);
			}

			if (!bKeepExtras && !bGlbOnly)
			{
				// Remove ancillary files (bin/png) if caller requested to keep only glb/gltf.
				TArray<FString> ExtraFiles;
				IFileManager::Get().FindFiles(ExtraFiles, *(AssetOutputDir / TEXT("*.bin")), true, false);
				TArray<FString> PngFiles;
				IFileManager::Get().FindFiles(PngFiles, *(AssetOutputDir / TEXT("*.png")), true, false);
				ExtraFiles.Append(PngFiles);
				for (const FString& Extra : ExtraFiles)
				{
					const FString FullPath = FPaths::Combine(AssetOutputDir, Extra);
					IFileManager::Get().Delete(*FullPath);
				}
			}

			Writer->WriteObjectEnd();

			if (MaxExports >= 0 && NumExported >= MaxExports)
			{
				break;
			}
		}

		if (MaxExports >= 0 && NumExported >= MaxExports)
		{
			break;
		}
	}

	Writer->WriteArrayEnd();
	Writer->WriteValue(TEXT("exported_count"), NumExported);
#else
	Writer->WriteValue(TEXT("status"), TEXT("editor_only"));
#endif

	Writer->WriteObjectEnd();
	Writer->Close();
	return FExecStatus::OK(MoveTemp(Out));
}

FExecStatus FLychSimObjectHandler::GetObjectRotation(
	const TArray<FString>& Pos,
    const TMap<FString,FString>& Kw,
    const TSet<FString>& Flags)
{
	// Build (RequestedId, Actor) pairs so we can report `not_found` against
	// the exact string the caller passed in, even when GetActorById returns
	// nullptr. For the -all flag every actor is real by construction.
	TArray<TPair<FString, AActor*>> Requested;
	if (Flags.Contains("all"))
	{
		TArray<AActor*> ActorList;
		UVisionBPLib::GetActorList(ActorList);
		for (AActor* Actor : ActorList)
		{
			Requested.Emplace(Actor ? Actor->GetName() : FString(), Actor);
		}
	}
	else
	{
		for (const FString& ActorId : Pos)
		{
			AActor* Actor = GetActorById(FUnrealcvServer::Get().GetWorld(), ActorId);
			Requested.Emplace(ActorId, Actor);
		}
	}

	const int32 Total = Requested.Num();
	TArray<FString> MissingIds;
	for (const TPair<FString, AActor*>& Entry : Requested)
	{
		if (!Entry.Value)
		{
			MissingIds.Add(Entry.Key);
		}
	}
	const int32 OkCount = Total - MissingIds.Num();

	FLychSimStructuredResponse R;
	R.BeginOutputs();

	for (const TPair<FString, AActor*>& Entry : Requested)
	{
		const FString& RequestedId = Entry.Key;
		AActor* Actor = Entry.Value;

		R.Writer()->WriteObjectStart();
		R.Writer()->WriteValue(TEXT("object_id"), *RequestedId);

		if (!Actor)
		{
			R.Writer()->WriteValue(TEXT("status"), TEXT("not_found"));
		}
		else
		{
			R.Writer()->WriteValue(TEXT("status"), TEXT("ok"));

			FActorController Controller(Actor);
			FRotator Rotation = Controller.GetRotation();

			R.Writer()->WriteArrayStart(TEXT("rotation"));
			R.Writer()->WriteValue(Rotation.Pitch); R.Writer()->WriteValue(Rotation.Yaw); R.Writer()->WriteValue(Rotation.Roll);
			R.Writer()->WriteArrayEnd();
		}

		R.Writer()->WriteObjectEnd();
	}

	FString ErrorMsg;
	if (MissingIds.Num() > 0)
	{
		const FString Joined = FString::Join(MissingIds, TEXT(", "));
		ErrorMsg = (OkCount == 0)
			? FString::Printf(TEXT("no objects found: %s"), *Joined)
			: FString::Printf(TEXT("%d of %d objects not found: %s"),
				MissingIds.Num(), Total, *Joined);
	}

	return R.FinishBatch(OkCount, Total, ErrorMsg);
}

FExecStatus FLychSimObjectHandler::SetObjectLocation(
	const TArray<FString>& Pos,
    const TMap<FString,FString>& Kw,
    const TSet<FString>& Flags)
{
	FLychSimStructuredResponse R;

	if (Pos.Num() < 4)
	{
		return R.Error(TEXT("expected: <obj_id> <x> <y> <z>"));
	}

	const FString& ActorId = Pos[0];

	AActor* Actor = GetActorById(FUnrealcvServer::Get().GetWorld(), ActorId);
	if (!Actor)
	{
		return R.Error(FString::Printf(TEXT("object not found: %s"), *ActorId));
	}

	FActorController Controller(Actor);
	float X = FCString::Atof(*Pos[1]), Y = FCString::Atof(*Pos[2]), Z = FCString::Atof(*Pos[3]);
	FVector NewLocation = FVector(X, Y, Z);
	Controller.SetLocation(NewLocation);

	return R.Ok();
}

FExecStatus FLychSimObjectHandler::SetObjectRotation(
	const TArray<FString>& Pos,
    const TMap<FString,FString>& Kw,
    const TSet<FString>& Flags)
{
	FLychSimStructuredResponse R;

	if (Pos.Num() < 4)
	{
		return R.Error(TEXT("expected: <obj_id> <pitch> <yaw> <roll>"));
	}

	const FString& ActorId = Pos[0];

	AActor* Actor = GetActorById(FUnrealcvServer::Get().GetWorld(), ActorId);
	if (!Actor)
	{
		return R.Error(FString::Printf(TEXT("object not found: %s"), *ActorId));
	}

	FActorController Controller(Actor);
	float Pitch = FCString::Atof(*Pos[1]), Yaw = FCString::Atof(*Pos[2]), Roll = FCString::Atof(*Pos[3]);
	FRotator Rotator = FRotator(Pitch, Yaw, Roll);
	Controller.SetRotation(Rotator);

	return R.Ok();
}

FExecStatus FLychSimObjectHandler::UpdateObject(
	const TArray<FString>& Pos,
    const TMap<FString,FString>& Kw,
    const TSet<FString>& Flags)
{
	FLychSimStructuredResponse R;

	FString ActorId;
	if (Pos.Num() > 0)
	{
		ActorId = Pos[0];
	}
	else
	{
		return R.Error(TEXT("object ID not specified"));
	}

	AActor* Actor = GetActorById(FUnrealcvServer::Get().GetWorld(), ActorId);
	if (!Actor)
	{
		return R.Error(FString::Printf(TEXT("object not found: %s"), *ActorId));
	}

	for (UActorComponent* Comp : Actor->GetComponents())
	{
		if (USceneComponent* SceneComp = Cast<USceneComponent>(Comp))
		{
			SceneComp->SetMobility(EComponentMobility::Movable);
		}
	}

	FActorController Controller(Actor);

	bool LocUpdated = false; bool RotUpdated = false;

	if (Kw.Contains(TEXT("loc")))
	{
		FString LocStr = Kw[TEXT("loc")];

		TArray<FString> Parts;
		LocStr.ParseIntoArray(Parts, TEXT(","), true);

		if (Parts.Num() == 3)
		{
			float X = FCString::Atof(*Parts[0]); float Y = FCString::Atof(*Parts[1]); float Z = FCString::Atof(*Parts[2]);
			FVector NewLocation = FVector(X, Y, Z);
			Controller.SetLocation(NewLocation);
		}
		else
		{
			return R.Error(TEXT("cannot parse loc: expected 3 comma-separated floats"));
		}
		LocUpdated = true;
	}

	if (Kw.Contains(TEXT("rot")))
	{
		FString RotStr = Kw[TEXT("rot")];

		TArray<FString> Parts;
		RotStr.ParseIntoArray(Parts, TEXT(","), true);

		if (Parts.Num() == 3)
		{
			float Pitch = FCString::Atof(*Parts[0]); float Yaw = FCString::Atof(*Parts[1]); float Roll = FCString::Atof(*Parts[2]);
			FRotator NewRotation = FRotator(Pitch, Yaw, Roll);
			Controller.SetRotation(NewRotation);
		}
		else
		{
			return R.Error(TEXT("cannot parse rot: expected 3 comma-separated floats"));
		}
		RotUpdated = true;
	}

	if (!LocUpdated && !RotUpdated)
	{
		return R.Error(TEXT("no properties to update: provide loc and/or rot"));
	}

	return R.Ok();
}

FExecStatus FLychSimObjectHandler::GetObjectAABB(
	const TArray<FString>& Pos,
    const TMap<FString,FString>& Kw,
    const TSet<FString>& Flags)
{
	// Build (RequestedId, Actor) pairs so `not_found` reports the exact
	// id the caller passed in, even when GetActorById returns nullptr.
	TArray<TPair<FString, AActor*>> Requested;
	if (Flags.Contains("all"))
	{
		TArray<AActor*> ActorList;
		UVisionBPLib::GetActorList(ActorList);
		for (AActor* Actor : ActorList)
		{
			Requested.Emplace(Actor ? Actor->GetName() : FString(), Actor);
		}
	}
	else
	{
		for (const FString& ActorId : Pos)
		{
			AActor* Actor = GetActorById(FUnrealcvServer::Get().GetWorld(), ActorId);
			Requested.Emplace(ActorId, Actor);
		}
	}

	const int32 Total = Requested.Num();
	TArray<FString> MissingIds;
	for (const TPair<FString, AActor*>& Entry : Requested)
	{
		if (!Entry.Value)
		{
			MissingIds.Add(Entry.Key);
		}
	}
	const int32 OkCount = Total - MissingIds.Num();

	FLychSimStructuredResponse R;
	R.BeginOutputs();

	for (const TPair<FString, AActor*>& Entry : Requested)
	{
		const FString& RequestedId = Entry.Key;
		AActor* Actor = Entry.Value;

		R.Writer()->WriteObjectStart();
		R.Writer()->WriteValue(TEXT("object_id"), *RequestedId);

		if (!Actor)
		{
			R.Writer()->WriteValue(TEXT("status"), TEXT("not_found"));
		}
		else
		{
			R.Writer()->WriteValue(TEXT("status"), TEXT("ok"));

			FActorController Controller(Actor);
			FBox AABB = Controller.GetAxisAlignedBoundingBox();

			R.Writer()->WriteArrayStart(TEXT("center"));
			R.Writer()->WriteValue(AABB.GetCenter().X);
			R.Writer()->WriteValue(AABB.GetCenter().Y);
			R.Writer()->WriteValue(AABB.GetCenter().Z);
			R.Writer()->WriteArrayEnd();

			R.Writer()->WriteArrayStart(TEXT("extent"));
			R.Writer()->WriteValue(AABB.GetExtent().X);
			R.Writer()->WriteValue(AABB.GetExtent().Y);
			R.Writer()->WriteValue(AABB.GetExtent().Z);
			R.Writer()->WriteArrayEnd();
		}

		R.Writer()->WriteObjectEnd();
	}

	FString ErrorMsg;
	if (MissingIds.Num() > 0)
	{
		const FString Joined = FString::Join(MissingIds, TEXT(", "));
		ErrorMsg = (OkCount == 0)
			? FString::Printf(TEXT("no objects found: %s"), *Joined)
			: FString::Printf(TEXT("%d of %d objects not found: %s"),
				MissingIds.Num(), Total, *Joined);
	}

	return R.FinishBatch(OkCount, Total, ErrorMsg);
}

FExecStatus FLychSimObjectHandler::GetObjectOBB(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;

	AActor* Actor = LychSimGetActor(Args);
	if (!Actor)
	{
		return R.Error(
			FString::Printf(TEXT("object not found: %s"),
				Args.Num() > 0 ? *Args[0] : TEXT("<empty>")));
	}

	FVector Center;
	FVector Extent;
	Actor->GetActorBounds(false, Center, Extent);
	FRotator Rotator = Actor->GetActorRotation();

	R.BeginOutputs();
	R.Writer()->WriteObjectStart();
	R.Writer()->WriteValue(TEXT("object_id"), Actor->GetName());
	R.Writer()->WriteValue(TEXT("status"), TEXT("ok"));

	R.Writer()->WriteArrayStart(TEXT("center"));
	R.Writer()->WriteValue(Center.X);
	R.Writer()->WriteValue(Center.Y);
	R.Writer()->WriteValue(Center.Z);
	R.Writer()->WriteArrayEnd();

	R.Writer()->WriteArrayStart(TEXT("extent"));
	R.Writer()->WriteValue(Extent.X);
	R.Writer()->WriteValue(Extent.Y);
	R.Writer()->WriteValue(Extent.Z);
	R.Writer()->WriteArrayEnd();

	R.Writer()->WriteArrayStart(TEXT("rotation"));
	R.Writer()->WriteValue(Rotator.Pitch);
	R.Writer()->WriteValue(Rotator.Yaw);
	R.Writer()->WriteValue(Rotator.Roll);
	R.Writer()->WriteArrayEnd();

	R.Writer()->WriteObjectEnd();

	return R.FinishBatch(1, 1, FString());
}

FExecStatus FLychSimObjectHandler::GetObjectAnnotationColor(
	const TArray<FString>& Pos,
    const TMap<FString,FString>& Kw,
    const TSet<FString>& Flags)
{
	// Build (RequestedId, Actor) pairs — same pattern as GetObjectLocation.
	TArray<TPair<FString, AActor*>> Requested;
	if (Flags.Contains("all"))
	{
		TArray<AActor*> ActorList;
		UVisionBPLib::GetActorList(ActorList);
		for (AActor* Actor : ActorList)
		{
			Requested.Emplace(Actor ? Actor->GetName() : FString(), Actor);
		}
	}
	else
	{
		for (const FString& ActorId : Pos)
		{
			AActor* Actor = GetActorById(FUnrealcvServer::Get().GetWorld(), ActorId);
			Requested.Emplace(ActorId, Actor);
		}
	}

	const int32 Total = Requested.Num();
	TArray<FString> MissingIds;
	for (const TPair<FString, AActor*>& Entry : Requested)
	{
		if (!Entry.Value)
		{
			MissingIds.Add(Entry.Key);
		}
	}
	const int32 OkCount = Total - MissingIds.Num();

	FLychSimStructuredResponse R;
	R.BeginOutputs();

	for (const TPair<FString, AActor*>& Entry : Requested)
	{
		const FString& RequestedId = Entry.Key;
		AActor* Actor = Entry.Value;

		R.Writer()->WriteObjectStart();
		R.Writer()->WriteValue(TEXT("object_id"), *RequestedId);

		if (!Actor)
		{
			R.Writer()->WriteValue(TEXT("status"), TEXT("not_found"));
		}
		else
		{
			R.Writer()->WriteValue(TEXT("status"), TEXT("ok"));

			FColor AnnotationColor;
			FActorController Controller(Actor);
			Controller.GetAnnotationColor(AnnotationColor);

			R.Writer()->WriteArrayStart(TEXT("color"));
			R.Writer()->WriteValue(AnnotationColor.R); R.Writer()->WriteValue(AnnotationColor.G);
			R.Writer()->WriteValue(AnnotationColor.B); R.Writer()->WriteValue(AnnotationColor.A);
			R.Writer()->WriteArrayEnd();
		}

		R.Writer()->WriteObjectEnd();
	}

	FString ErrorMsg;
	if (MissingIds.Num() > 0)
	{
		const FString Joined = FString::Join(MissingIds, TEXT(", "));
		ErrorMsg = (OkCount == 0)
			? FString::Printf(TEXT("no objects found: %s"), *Joined)
			: FString::Printf(TEXT("%d of %d objects not found: %s"),
				MissingIds.Num(), Total, *Joined);
	}

	return R.FinishBatch(OkCount, Total, ErrorMsg);
}

FExecStatus FLychSimObjectHandler::GetObjectAnnotations(
	const TArray<FString>& Pos,
    const TMap<FString,FString>& Kw,
    const TSet<FString>& Flags)
{
	TArray<TPair<FString, AActor*>> Requested;
	if (Flags.Contains("all"))
	{
		TArray<AActor*> ActorList;
		UVisionBPLib::GetActorList(ActorList);
		for (AActor* Actor : ActorList)
		{
			Requested.Emplace(Actor ? Actor->GetName() : FString(), Actor);
		}
	}
	else
	{
		for (const FString& ActorId : Pos)
		{
			AActor* Actor = GetActorById(FUnrealcvServer::Get().GetWorld(), ActorId);
			Requested.Emplace(ActorId, Actor);
		}
	}

	const int32 Total = Requested.Num();
	TArray<FString> MissingIds;
	for (const TPair<FString, AActor*>& Entry : Requested)
	{
		if (!Entry.Value)
		{
			MissingIds.Add(Entry.Key);
		}
	}
	const int32 OkCount = Total - MissingIds.Num();

	FLychSimStructuredResponse R;
	R.BeginOutputs();

	for (const TPair<FString, AActor*>& Entry : Requested)
	{
		const FString& RequestedId = Entry.Key;
		AActor* Actor = Entry.Value;

		R.Writer()->WriteObjectStart();
		R.Writer()->WriteValue(TEXT("object_id"), *RequestedId);

		if (!Actor)
		{
			R.Writer()->WriteValue(TEXT("status"), TEXT("not_found"));
		}
		else
		{
			R.Writer()->WriteValue(TEXT("status"), TEXT("ok"));

#if WITH_EDITOR
			FGuid Guid = Actor->GetActorGuid();
			R.Writer()->WriteValue(TEXT("guid"),
				Guid.IsValid() ? Guid.ToString() : FString(TEXT("NO_GUID")));
#else
			R.Writer()->WriteValue(TEXT("guid"), TEXT("NO_GUID"));
#endif

			FActorController Controller(Actor);

			FBox AABB = Controller.GetAxisAlignedBoundingBox();
			R.Writer()->WriteObjectStart(TEXT("aabb"));
			R.Writer()->WriteArrayStart(TEXT("center"));
			R.Writer()->WriteValue(AABB.GetCenter().X);
			R.Writer()->WriteValue(AABB.GetCenter().Y);
			R.Writer()->WriteValue(AABB.GetCenter().Z);
			R.Writer()->WriteArrayEnd();
			R.Writer()->WriteArrayStart(TEXT("extent"));
			R.Writer()->WriteValue(AABB.GetExtent().X);
			R.Writer()->WriteValue(AABB.GetExtent().Y);
			R.Writer()->WriteValue(AABB.GetExtent().Z);
			R.Writer()->WriteArrayEnd();
			R.Writer()->WriteObjectEnd();

			FVector Center;
			FVector Extent;
			Actor->GetActorBounds(false, Center, Extent);
			FRotator Rotator = Actor->GetActorRotation();
			R.Writer()->WriteObjectStart(TEXT("obb"));
			R.Writer()->WriteArrayStart(TEXT("center"));
			R.Writer()->WriteValue(Center.X);
			R.Writer()->WriteValue(Center.Y);
			R.Writer()->WriteValue(Center.Z);
			R.Writer()->WriteArrayEnd();
			R.Writer()->WriteArrayStart(TEXT("extent"));
			R.Writer()->WriteValue(Extent.X);
			R.Writer()->WriteValue(Extent.Y);
			R.Writer()->WriteValue(Extent.Z);
			R.Writer()->WriteArrayEnd();
			R.Writer()->WriteArrayStart(TEXT("rotation"));
			R.Writer()->WriteValue(Rotator.Pitch);
			R.Writer()->WriteValue(Rotator.Yaw);
			R.Writer()->WriteValue(Rotator.Roll);
			R.Writer()->WriteArrayEnd();
			R.Writer()->WriteObjectEnd();

			bool bOnlyCollidingComponents = false;
			Actor->GetActorBounds(bOnlyCollidingComponents, Center, Extent);
			R.Writer()->WriteObjectStart(TEXT("bounds"));
			R.Writer()->WriteArrayStart(TEXT("center"));
			R.Writer()->WriteValue(Center.X);
			R.Writer()->WriteValue(Center.Y);
			R.Writer()->WriteValue(Center.Z);
			R.Writer()->WriteArrayEnd();
			R.Writer()->WriteArrayStart(TEXT("extent"));
			R.Writer()->WriteValue(Extent.X);
			R.Writer()->WriteValue(Extent.Y);
			R.Writer()->WriteValue(Extent.Z);
			R.Writer()->WriteArrayEnd();
			R.Writer()->WriteObjectEnd();

			bOnlyCollidingComponents = true;
			Actor->GetActorBounds(bOnlyCollidingComponents, Center, Extent);
			R.Writer()->WriteObjectStart(TEXT("bounds_tight"));
			R.Writer()->WriteArrayStart(TEXT("center"));
			R.Writer()->WriteValue(Center.X);
			R.Writer()->WriteValue(Center.Y);
			R.Writer()->WriteValue(Center.Z);
			R.Writer()->WriteArrayEnd();
			R.Writer()->WriteArrayStart(TEXT("extent"));
			R.Writer()->WriteValue(Extent.X);
			R.Writer()->WriteValue(Extent.Y);
			R.Writer()->WriteValue(Extent.Z);
			R.Writer()->WriteArrayEnd();
			R.Writer()->WriteObjectEnd();

			FVector Location = Controller.GetLocation();
			R.Writer()->WriteArrayStart(TEXT("location"));
			R.Writer()->WriteValue(Location.X); R.Writer()->WriteValue(Location.Y); R.Writer()->WriteValue(Location.Z);
			R.Writer()->WriteArrayEnd();

			FRotator Rotation = Controller.GetRotation();
			R.Writer()->WriteArrayStart(TEXT("rotation"));
			R.Writer()->WriteValue(Rotation.Pitch); R.Writer()->WriteValue(Rotation.Yaw); R.Writer()->WriteValue(Rotation.Roll);
			R.Writer()->WriteArrayEnd();

			FVector Scale = Actor->GetActorScale3D();
			R.Writer()->WriteArrayStart(TEXT("scale"));
			R.Writer()->WriteValue(Scale.X); R.Writer()->WriteValue(Scale.Y); R.Writer()->WriteValue(Scale.Z);
			R.Writer()->WriteArrayEnd();

			FColor AnnotationColor;
			Controller.GetAnnotationColor(AnnotationColor);
			R.Writer()->WriteArrayStart(TEXT("color"));
			R.Writer()->WriteValue(AnnotationColor.R); R.Writer()->WriteValue(AnnotationColor.G);
			R.Writer()->WriteValue(AnnotationColor.B); R.Writer()->WriteValue(AnnotationColor.A);
			R.Writer()->WriteArrayEnd();

			FString AssetPath = GetAssetPath(Actor);
			R.Writer()->WriteValue(TEXT("asset_path"), AssetPath);
		}

		R.Writer()->WriteObjectEnd();
	}

	FString ErrorMsg;
	if (MissingIds.Num() > 0)
	{
		const FString Joined = FString::Join(MissingIds, TEXT(", "));
		ErrorMsg = (OkCount == 0)
			? FString::Printf(TEXT("no objects found: %s"), *Joined)
			: FString::Printf(TEXT("%d of %d objects not found: %s"),
				MissingIds.Num(), Total, *Joined);
	}

	return R.FinishBatch(OkCount, Total, ErrorMsg);
}

FExecStatus FLychSimObjectHandler::AddObject(
	const TArray<FString>& Pos,
    const TMap<FString,FString>& Kw,
    const TSet<FString>& Flags)
{
	FLychSimStructuredResponse R;

	FString ObjectName, ObjectPath;
	float X = 0.0f, Y = 0.0f, Z = 0.0f;
	float Pitch = 0.0f, Yaw = 0.0f, Roll = 0.0f;
	float ScaleFactor = 1.0f;

	if (Pos.Num() == 2) { ObjectName = Pos[0]; ObjectPath = Pos[1]; }
	else if (Pos.Num() == 5) {
		ObjectName = Pos[0];
		ObjectPath = Pos[1];
		X = FCString::Atof(*Pos[2]);
		Y = FCString::Atof(*Pos[3]);
		Z = FCString::Atof(*Pos[4]);
	}
	else if (Pos.Num() == 8) {
		ObjectName = Pos[0];
		ObjectPath = Pos[1];
		X = FCString::Atof(*Pos[2]);
		Y = FCString::Atof(*Pos[3]);
		Z = FCString::Atof(*Pos[4]);
		Pitch = FCString::Atof(*Pos[5]);
		Yaw = FCString::Atof(*Pos[6]);
		Roll = FCString::Atof(*Pos[7]);
	}
	else if (Pos.Num() == 9) {
		ObjectName = Pos[0];
		ObjectPath = Pos[1];
		X = FCString::Atof(*Pos[2]);
		Y = FCString::Atof(*Pos[3]);
		Z = FCString::Atof(*Pos[4]);
		Pitch = FCString::Atof(*Pos[5]);
		Yaw = FCString::Atof(*Pos[6]);
		Roll = FCString::Atof(*Pos[7]);
		ScaleFactor = FCString::Atof(*Pos[8]);
	}
	else {
		return R.Error(TEXT("expected 2, 5, 8, or 9 positional args: <name> <path> [x y z] [p y r] [scale]"));
	}

	FVector Location(X, Y, Z);
	FRotator Rotation(Pitch, Yaw, Roll);
	FVector Scale(ScaleFactor, ScaleFactor, ScaleFactor);
	FTransform SpawnTransform(Rotation, Location, Scale);

	UWorld* World = nullptr;
#if WITH_EDITOR
	if (GEditor)
	{
		if (GEditor->PlayWorld)
		{
			World = GEditor->PlayWorld;
		}
		else
		{
			World = GEditor->GetEditorWorldContext().World();
		}
	}
#else
	World = FUnrealcvServer::Get().GetWorld();
#endif

	if (!World) {
		return R.Error(TEXT("no valid world context available"));
	}

	if (ExistsActor(World, ObjectName))
	{
		return R.Error(FString::Printf(TEXT("an object named '%s' already exists"), *ObjectName));
	}

	FActorSpawnParameters SpawnParams;
	SpawnParams.Name = FName(*ObjectName);

	if (Flags.Contains("skipIfColliding"))
	{
		SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::DontSpawnIfColliding;
	}
	else if (Flags.Contains("adjustIfPossible"))
	{
		SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButDontSpawnIfColliding;
	}

	// Try loading as a blueprint class
	FString BPObjectPath = TEXT("Class'") + ObjectPath + TEXT("_C'");
	UClass* BPClass = LoadObject<UClass>(nullptr, *BPObjectPath);

	if (BPClass)
	{
		UE_LOG(LogLychSim, Log, TEXT("Spawning blueprint actor from %s"), *BPObjectPath);
		AActor* NewActor = World->SpawnActor<AActor>(
			BPClass, SpawnTransform, SpawnParams
		);
		if (!NewActor)
		{
			return R.Error(FString::Printf(TEXT("SpawnActor failed for blueprint %s"), *ObjectPath));
		}

		if (Flags.Contains("lockRotation"))
		{
			LockRotation(NewActor);
		}
	}
	else
	{
		UE_LOG(LogLychSim, Log, TEXT("Spawning basic actor with mesh from %s"), *ObjectPath);

		if (ObjectPath.Contains(TEXT("SKM")))
		{
			ALychSimSkeletalActor* NewActor = World->SpawnActor<ALychSimSkeletalActor>(
				ALychSimSkeletalActor::StaticClass(), SpawnTransform, SpawnParams
			);
			if (!NewActor)
			{
				return R.Error(FString::Printf(TEXT("SpawnActor failed for skeletal mesh %s"), *ObjectPath));
			}
			NewActor->InitializeMesh(ObjectPath);

			if (Flags.Contains("lockRotation"))
			{
				LockRotation(NewActor);
			}
		}
		else
		{
			ALychSimBasicActor* NewActor = World->SpawnActor<ALychSimBasicActor>(
				ALychSimBasicActor::StaticClass(), SpawnTransform, SpawnParams
			);
			if (!NewActor)
			{
				return R.Error(FString::Printf(TEXT("SpawnActor failed for static mesh %s"), *ObjectPath));
			}
			NewActor->InitializeMesh(ObjectPath);

			if (Flags.Contains("lockRotation"))
			{
				LockRotation(NewActor);
			}
		}
	}

	TWeakObjectPtr<AUnrealcvWorldController> WorldController = FUnrealcvServer::Get().WorldController;
	if (WorldController.IsValid() && WorldController->IsAnnotationsReady())
	{
		WorldController->AnnotateNewObjects();
	}

	return R.Ok();
}

FExecStatus FLychSimObjectHandler::GetMeshExtent(
	const TArray<FString>& Pos,
    const TMap<FString,FString>& Kw,
    const TSet<FString>& Flags)
{
	FLychSimStructuredResponse R;
	R.BeginOutputs();

	auto WriteExtent = [&R](const FVector& Extent)
	{
		R.Writer()->WriteValue(TEXT("status"), TEXT("ok"));
		R.Writer()->WriteArrayStart(TEXT("extent"));
		R.Writer()->WriteValue(Extent.X);
		R.Writer()->WriteValue(Extent.Y);
		R.Writer()->WriteValue(Extent.Z);
		R.Writer()->WriteArrayEnd();
	};

	auto ExtentFromComponents = [](AActor* DefaultActor) -> FVector
	{
		FBox CombinedBox(ForceInit);
		TArray<UActorComponent*> Components = DefaultActor->GetComponents().Array();
		for (UActorComponent* Comp : Components)
		{
			if (const UPrimitiveComponent* Prim = Cast<UPrimitiveComponent>(Comp))
			{
				const FBoxSphereBounds Bounds = Prim->CalcBounds(FTransform::Identity);
				CombinedBox += Bounds.GetBox();
			}
		}
		return CombinedBox.GetExtent();
	};

	const int32 Total = Pos.Num();
	int32 OkCount = 0;
	TArray<FString> MissingPaths;

	for (const FString& AssetPath : Pos)
	{
		R.Writer()->WriteObjectStart();
		R.Writer()->WriteValue(TEXT("mesh_path"), *AssetPath);

		bool bEntryOk = false;

		if (UBlueprint* BP = LoadObject<UBlueprint>(nullptr, *AssetPath))
		{
			if (AActor* DefaultActor = Cast<AActor>(BP->GeneratedClass->GetDefaultObject()))
			{
				WriteExtent(ExtentFromComponents(DefaultActor));
				bEntryOk = true;
			}
			else
			{
				R.Writer()->WriteValue(TEXT("status"), TEXT("default_object_not_actor"));
			}
		}
		else if (UBlueprintGeneratedClass* BPGC = LoadObject<UBlueprintGeneratedClass>(nullptr, *AssetPath))
		{
			if (AActor* DefaultActor = Cast<AActor>(BPGC->GetDefaultObject()))
			{
				WriteExtent(ExtentFromComponents(DefaultActor));
				bEntryOk = true;
			}
			else
			{
				R.Writer()->WriteValue(TEXT("status"), TEXT("default_object_not_actor"));
			}
		}
		else if (UStaticMesh* SM = LoadObject<UStaticMesh>(nullptr, *AssetPath))
		{
			WriteExtent(SM->GetBounds().BoxExtent);
			bEntryOk = true;
		}
		else if (USkeletalMesh* SK = LoadObject<USkeletalMesh>(nullptr, *AssetPath))
		{
			WriteExtent(SK->GetBounds().BoxExtent);
			bEntryOk = true;
		}
		else
		{
			R.Writer()->WriteValue(TEXT("status"), TEXT("not_found"));
		}

		R.Writer()->WriteObjectEnd();

		if (bEntryOk) { ++OkCount; }
		else          { MissingPaths.Add(AssetPath); }
	}

	FString ErrorMsg;
	if (MissingPaths.Num() > 0)
	{
		const FString Joined = FString::Join(MissingPaths, TEXT(", "));
		ErrorMsg = (OkCount == 0)
			? FString::Printf(TEXT("no meshes loaded: %s"), *Joined)
			: FString::Printf(TEXT("%d of %d meshes not loaded: %s"),
				MissingPaths.Num(), Total, *Joined);
	}

	return R.FinishBatch(OkCount, Total, ErrorMsg);
}

FExecStatus FLychSimObjectHandler::DestroyObject(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;

	AActor* Actor = LychSimGetActor(Args);
	if (!Actor)
	{
		return R.Error(
			FString::Printf(TEXT("object not found: %s"),
				Args.Num() > 0 ? *Args[0] : TEXT("<empty>")));
	}

	Actor->Destroy();
	return R.Ok();
}

FExecStatus FLychSimObjectHandler::SetObjectMaterial(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;

	if (Args.Num() != 3)
	{
		return R.Error(TEXT("expected 3 args: <obj_id> <material_path> <element_idx>"));
	}

	const FString& ObjectName = Args[0];
	const FString& MaterialPath = Args[1];
	int ElementIdx = FCString::Atoi(*Args[2]);

	AActor* Actor = LychSimGetActor(Args);
	if (!Actor)
	{
		return R.Error(FString::Printf(TEXT("object not found: %s"), *ObjectName));
	}

	UMeshComponent* MC = Actor->FindComponentByClass<UMeshComponent>();
	if (!MC)
	{
		return R.Error(FString::Printf(TEXT("no mesh component on %s"), *ObjectName));
	}

	UMaterialInterface* MI = Cast<UMaterialInterface>(
		StaticLoadObject(UMaterialInterface::StaticClass(), nullptr, *MaterialPath));
	if (!MI)
	{
		return R.Error(FString::Printf(TEXT("material not found: %s"), *MaterialPath));
	}

	MC->SetMaterial(ElementIdx, MI);
	return R.Ok();
}

FExecStatus FLychSimObjectHandler::GetObjectIDFromSelection(const TArray<FString>& Args)
{
	FLychSimStructuredResponse R;

#if WITH_EDITOR
	if (!GEditor)
	{
		return R.Error(TEXT("editor not available"));
	}

	USelection* SelectedActors = GEditor->GetSelectedActors();
	if (!SelectedActors || SelectedActors->Num() == 0)
	{
		return R.Error(TEXT("no actor selected in editor"));
	}

	R.BeginOutputs();
	int32 Count = 0;

	for (FSelectionIterator It(*SelectedActors); It; ++It)
	{
		if (AActor* Actor = Cast<AActor>(*It))
		{
			R.Writer()->WriteObjectStart();
			R.Writer()->WriteValue(TEXT("object_id"), Actor->GetName());

			FGuid Guid = Actor->GetActorGuid();
			R.Writer()->WriteValue(TEXT("guid"),
				Guid.IsValid() ? Guid.ToString() : FString(TEXT("NO_GUID")));

			R.Writer()->WriteObjectEnd();
			++Count;
		}
	}

	return R.FinishBatch(Count, Count, FString());
#else
	return R.Error(TEXT("editor-only command; not available in non-editor builds"));
#endif
}

FExecStatus FLychSimObjectHandler::AdjustLight(
	const TArray<FString>& Pos,
    const TMap<FString,FString>& Kw,
    const TSet<FString>& Flags)
{
	FLychSimStructuredResponse R;

	FString ActorId;
	if (Pos.Num() > 0)
	{
		ActorId = Pos[0];
	}
	else
	{
		return R.Error(TEXT("light object ID not specified"));
	}

	UWorld* World = FUnrealcvServer::Get().GetWorld();

	ADirectionalLight* Sun = nullptr;
	for (TActorIterator<ADirectionalLight> It(World); It; ++It)
	{
		Sun = *It;
		if (!Sun) continue;

		if (Sun->GetWorld() == World && Sun->GetName() == ActorId) break;
	}

	if (!Sun)
	{
		return R.Error(FString::Printf(TEXT("light object not found: %s"), *ActorId));
	}

	UDirectionalLightComponent* Comp = Cast<UDirectionalLightComponent>(Sun->GetLightComponent());
	if (!Comp)
	{
		return R.Error(FString::Printf(TEXT("light component not found on %s"), *ActorId));
	}

	if (Kw.Contains(TEXT("intensity")))
	{
		float Intensity = FCString::Atof(*Kw[TEXT("intensity")]);
		Comp->SetIntensity(Intensity);
		Comp->MarkRenderStateDirty();
	}

	if (Kw.Contains(TEXT("rot")))
	{
		FString RotStr = Kw[TEXT("rot")];

		TArray<FString> Parts;
		RotStr.ParseIntoArray(Parts, TEXT(","), true);

		if (Parts.Num() == 3)
		{
			float Pitch = FCString::Atof(*Parts[0]); float Yaw = FCString::Atof(*Parts[1]); float Roll = FCString::Atof(*Parts[2]);
			FRotator NewRotation = FRotator(Pitch, Yaw, Roll);
			Sun->SetActorRotation(NewRotation);
			Comp->MarkRenderStateDirty();
		}
		else
		{
			return R.Error(TEXT("cannot parse rot: expected 3 comma-separated floats"));
		}
	}

	if (Kw.Contains(TEXT("color")))
	{
		FString ColorStr = Kw[TEXT("color")];

		TArray<FString> Parts;
		ColorStr.ParseIntoArray(Parts, TEXT(","), true);

		if (Parts.Num() == 3)
		{
			float LC_R = FCString::Atof(*Parts[0]); float LC_G = FCString::Atof(*Parts[1]); float LC_B = FCString::Atof(*Parts[2]);
			FLinearColor NewColor = FLinearColor(LC_R, LC_G, LC_B);
			Comp->SetLightColor(NewColor);
			Comp->MarkRenderStateDirty();
		}
		else
		{
			return R.Error(TEXT("cannot parse color: expected 3 comma-separated floats"));
		}
	}

	if (Kw.Contains(TEXT("temp")))
	{
		int TempK = FCString::Atoi(*Kw[TEXT("temp")]);
		Comp->SetTemperature(TempK);
		Comp->MarkRenderStateDirty();
	}

	return R.Ok();
}
