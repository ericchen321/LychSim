#include "LychSimDataHandler.h"

#include "Controller/ActorController.h"
#include "CameraHandler.h"
#include "FusionCamSensor.h"
#include "ImageUtil.h"
#include "SensorBPLib.h"
#include "Serialization.h"
#include "Utils/DataUtil.h"
#include "Utils/StrFormatter.h"
#include "Utils/UObjectUtils.h"
#include "UnrealcvLog.h"

#include "Serialization/JsonWriter.h"
#include "Serialization/JsonSerializer.h"
#if WITH_EDITOR
#include "Editor.h"
#include "ScopedTransaction.h"
#include "Editor/UnrealEdEngine.h"
#include "UnrealEdGlobals.h"
#include "Selection.h"
#endif
#include "GameFramework/Actor.h"

#include "DrawDebugHelpers.h"
#include "Kismet/GameplayStatics.h"

void FLychSimDataHandler::RegisterCommands() {
	CommandDispatcher->BindCommandUE(
		"lych data info",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimDataHandler::CollectInfo),
		"Get info about selected object."
	);

	CommandDispatcher->BindCommandUE(
		"lych data debug_line",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimDataHandler::LSDrawDebugLine),
		"Draw a debug line connecting the center of a list of objects."
	);

	CommandDispatcher->BindCommandUE(
		"lych data debug_line_pts",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimDataHandler::LSDrawDebugLinePts),
		"Draw a debug line connecting a list of 3D points."
	);

	CommandDispatcher->BindCommandUE(
		"lych data clear_debug_lines",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimDataHandler::LSClearDebugLines),
		"Clear all debug annotations."
	);

	CommandDispatcher->BindCommandUE(
		"lych data pause",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimDataHandler::LSPause),
		"Pause the game."
	);

	CommandDispatcher->BindCommandUE(
		"lych data unpause",
		FDispatcherDelegateUE::CreateRaw(this, &FLychSimDataHandler::LSUnPause),
		"Unpause the game."
	);
}

static const TMap<FString, FColor>& GetColorMap()
{
    static TMap<FString, FColor> Map;
    if (Map.Num() == 0)
    {
        Map.Add(TEXT("white"),      FColor::White);
        Map.Add(TEXT("black"),      FColor::Black);
        Map.Add(TEXT("transparent"),FColor::Transparent);
        Map.Add(TEXT("red"),        FColor::Red);
        Map.Add(TEXT("green"),      FColor::Green);
        Map.Add(TEXT("blue"),       FColor::Blue);
        Map.Add(TEXT("yellow"),     FColor::Yellow);
        Map.Add(TEXT("cyan"),       FColor::Cyan);
        Map.Add(TEXT("magenta"),    FColor::Magenta);
        Map.Add(TEXT("orange"),     FColor::Orange);
        Map.Add(TEXT("purple"),     FColor::Purple);
        Map.Add(TEXT("turquoise"),  FColor::Turquoise);
        Map.Add(TEXT("silver"),     FColor::Silver);
        Map.Add(TEXT("emerald"),    FColor::Emerald);
    }
    return Map;
}

FExecStatus FLychSimDataHandler::CollectInfo(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags)
{
	FString Out;
	TSharedRef< TJsonWriter<> > Writer = TJsonWriterFactory<>::Create(&Out);

	Writer->WriteObjectStart();

#if WITH_EDITOR
	if (!GEditor)
	{
		Writer->WriteValue(TEXT("status"), TEXT("Editor not found"));
		Writer->WriteObjectEnd();
		Writer->Close();
		return FExecStatus::OK(MoveTemp(Out));
	}

	USelection* SelectedActors = GEditor->GetSelectedActors();
    if (!SelectedActors || SelectedActors->Num() == 0)
    {
        Writer->WriteValue(TEXT("status"), TEXT("No actor selected in editor"));
		Writer->WriteObjectEnd();
		Writer->Close();
		return FExecStatus::OK(MoveTemp(Out));
    }

	Writer->WriteValue(TEXT("status"), TEXT("ok"));
	Writer->WriteArrayStart(TEXT("outputs"));

	for (FSelectionIterator It(*SelectedActors); It; ++It)
	{
		if (AActor* Actor = Cast<AActor>(*It))
		{
			Writer->WriteObjectStart();
			Writer->WriteValue(TEXT("object_id"), *Actor->GetName());

			Writer->WriteValue(TEXT("status"), TEXT("ok"));

			FGuid Guid = Actor->GetActorGuid();
			if (Guid.IsValid())
			{
				Writer->WriteValue(TEXT("guid"), *Guid.ToString());
			}
			else
			{
				Writer->WriteValue(TEXT("guid"), TEXT("NO_GUID"));
			}

			FActorController Controller(Actor);

			FBox AABB = Controller.GetAxisAlignedBoundingBox();
			Writer->WriteObjectStart(TEXT("aabb"));
			Writer->WriteArrayStart(TEXT("center"));
        	Writer->WriteValue(AABB.GetCenter().X);
        	Writer->WriteValue(AABB.GetCenter().Y);
        	Writer->WriteValue(AABB.GetCenter().Z);
        	Writer->WriteArrayEnd();
			Writer->WriteArrayStart(TEXT("extent"));
			Writer->WriteValue(AABB.GetExtent().X);
			Writer->WriteValue(AABB.GetExtent().Y);
			Writer->WriteValue(AABB.GetExtent().Z);
			Writer->WriteArrayEnd();
			Writer->WriteObjectEnd();

			FVector Center;
			FVector Extent;
			Actor->GetActorBounds(false, Center, Extent);
			FRotator Rotator = Actor->GetActorRotation();
			Writer->WriteObjectStart(TEXT("obb"));
			Writer->WriteArrayStart(TEXT("center"));
        	Writer->WriteValue(Center.X);
        	Writer->WriteValue(Center.Y);
        	Writer->WriteValue(Center.Z);
        	Writer->WriteArrayEnd();
			Writer->WriteArrayStart(TEXT("extent"));
			Writer->WriteValue(Extent.X);
			Writer->WriteValue(Extent.Y);
			Writer->WriteValue(Extent.Z);
			Writer->WriteArrayEnd();
			Writer->WriteArrayStart(TEXT("rotation"));
			Writer->WriteValue(Rotator.Pitch);
			Writer->WriteValue(Rotator.Yaw);
			Writer->WriteValue(Rotator.Roll);
			Writer->WriteArrayEnd();
			Writer->WriteObjectEnd();

			bool bOnlyCollidingComponents = false;
			Actor->GetActorBounds(bOnlyCollidingComponents, Center, Extent);
			Writer->WriteObjectStart(TEXT("bounds"));
			Writer->WriteArrayStart(TEXT("center"));
			Writer->WriteValue(Center.X);
			Writer->WriteValue(Center.Y);
			Writer->WriteValue(Center.Z);
			Writer->WriteArrayEnd();
			Writer->WriteArrayStart(TEXT("extent"));
			Writer->WriteValue(Extent.X);
			Writer->WriteValue(Extent.Y);
			Writer->WriteValue(Extent.Z);
			Writer->WriteArrayEnd();
			Writer->WriteObjectEnd();

			FVector Location = Controller.GetLocation();
			Writer->WriteArrayStart(TEXT("location"));
			Writer->WriteValue(Location.X); Writer->WriteValue(Location.Y); Writer->WriteValue(Location.Z);
			Writer->WriteArrayEnd();

			FRotator Rotation = Controller.GetRotation();
			Writer->WriteArrayStart(TEXT("rotation"));
			Writer->WriteValue(Rotation.Pitch); Writer->WriteValue(Rotation.Yaw); Writer->WriteValue(Rotation.Roll);
			Writer->WriteArrayEnd();

			FVector Scale = Actor->GetActorScale3D();
			Writer->WriteArrayStart(TEXT("scale"));
			Writer->WriteValue(Scale.X); Writer->WriteValue(Scale.Y); Writer->WriteValue(Scale.Z);
			Writer->WriteArrayEnd();

			FColor AnnotationColor;
			Controller.GetAnnotationColor(AnnotationColor);
			Writer->WriteArrayStart(TEXT("color"));
        	Writer->WriteValue(AnnotationColor.R); Writer->WriteValue(AnnotationColor.G);
			Writer->WriteValue(AnnotationColor.B); Writer->WriteValue(AnnotationColor.A);
        	Writer->WriteArrayEnd();

			Writer->WriteObjectEnd();
		}
	}

	Writer->WriteArrayEnd();
	Writer->WriteObjectEnd();
	Writer->Close();
	return FExecStatus::OK(MoveTemp(Out));
#else
	Writer->WriteValue(TEXT("status"), TEXT("Running CollectInfo from outside editor"));
	Writer->WriteObjectEnd();
	Writer->Close();
	return FExecStatus::OK(MoveTemp(Out));
#endif
}

FExecStatus FLychSimDataHandler::LSDrawDebugLine(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags)
{
	FString Out;
    TSharedRef< TJsonWriter<> > Writer = TJsonWriterFactory<>::Create(&Out);
	Writer->WriteObjectStart();

#if WITH_EDITOR
	TArray<AActor*> ActorList;
	for (const FString& ActorId : Pos)
	{
		AActor* Actor = GetActorById(FUnrealcvServer::Get().GetWorld(), ActorId);
		if (!IsValid(Actor))
		{
			Writer->WriteValue(TEXT("status"), TEXT("Actor not valid: ") + ActorId);
			Writer->WriteObjectEnd();
			Writer->Close();
			return FExecStatus::OK(MoveTemp(Out));
		}
		ActorList.Add(Actor);
	}

	if (ActorList.Num() < 2)
	{
		Writer->WriteValue(TEXT("status"), TEXT("Need at least two actors to draw a line"));
		Writer->WriteObjectEnd();
		Writer->Close();
		return FExecStatus::OK(MoveTemp(Out));
	}

	UWorld* World = ActorList[0]->GetWorld();

	TArray<FVector> Centers;
    Centers.Reserve(ActorList.Num());

	for (AActor* Actor : ActorList)
	{
		FActorController Controller(Actor);
		FBox AABB = Controller.GetAxisAlignedBoundingBox();
		Centers.Add(AABB.GetCenter());
	}

	FColor Color;
	const FString* ColorName = Kw.Find(TEXT("color"));
	if (!ColorName)
	{
		Color = FColor::Green;
	}
	else
	{
		const FColor* FoundColor = GetColorMap().Find(ColorName->ToLower());
		if (!FoundColor)
		{
			Writer->WriteValue(TEXT("status"), TEXT("Color not recognized: ") + *ColorName);
			Writer->WriteObjectEnd();
			Writer->Close();
			return FExecStatus::OK(MoveTemp(Out));
		}
		Color = *FoundColor;
	}

	for (const FVector& C : Centers)
    {
        DrawDebugSphere(
            World, C,
            /*Radius=*/8.f,
            /*Segments=*/12,
            Color,
            /*bPersistentLines=*/true,
            /*LifeTime=*/-1.f,
            /*DepthPriority=*/0,
            /*Thickness=*/1.5f
        );
    }

	for (int32 i = 0; i + 1 < Centers.Num(); ++i)
    {
        DrawDebugDirectionalArrow(
            World,
            Centers[i],
            Centers[i + 1],
			/*ArrowSize=*/30.0f,
            Color,
            /*bPersistentLines=*/true,
            /*LifeTime=*/-1.f,
            /*DepthPriority=*/0,
            /*Thickness=*/2.0f
        );
    }

	Writer->WriteValue(TEXT("status"), TEXT("ok"));
	Writer->WriteObjectEnd();
	Writer->Close();
	return FExecStatus::OK(MoveTemp(Out));
#else
	Writer->WriteValue(TEXT("status"), TEXT("Running DrawDebugLine from outside editor"));
	Writer->WriteObjectEnd();
	Writer->Close();
	return FExecStatus::OK(MoveTemp(Out));
#endif
}

FExecStatus FLychSimDataHandler::LSDrawDebugLinePts(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags)
{
	FString Out;
    TSharedRef< TJsonWriter<> > Writer = TJsonWriterFactory<>::Create(&Out);
	Writer->WriteObjectStart();

#if WITH_EDITOR
	const int32 NumPos = Pos.Num();
	if (NumPos % 3 != 0)
	{
		Writer->WriteValue(TEXT("status"), TEXT("Number of positional arguments should be a multiple of three"));
		Writer->WriteObjectEnd();
		Writer->Close();
		return FExecStatus::OK(MoveTemp(Out));
	}

	const int32 NumPts = Pos.Num() / 3;
	if (NumPts < 2)
	{
		Writer->WriteValue(TEXT("status"), TEXT("Need at least two points to draw a line"));
		Writer->WriteObjectEnd();
		Writer->Close();
		return FExecStatus::OK(MoveTemp(Out));
	}

	TArray<FVector> Centers;
	Centers.Reserve(NumPts);
	for (int32 i = 0; i < NumPts; ++i)
	{
		const float X = FCString::Atof(*Pos[i * 3 + 0]);
		const float Y = FCString::Atof(*Pos[i * 3 + 1]);
		const float Z = FCString::Atof(*Pos[i * 3 + 2]);
		Centers.Emplace(X, Y, Z);
	}

	FColor Color;
	const FString* ColorName = Kw.Find(TEXT("color"));
	if (!ColorName)
	{
		Color = FColor::Green;
	}
	else
	{
		const FColor* FoundColor = GetColorMap().Find(ColorName->ToLower());
		if (!FoundColor)
		{
			Writer->WriteValue(TEXT("status"), TEXT("Color not recognized: ") + *ColorName);
			Writer->WriteObjectEnd();
			Writer->Close();
			return FExecStatus::OK(MoveTemp(Out));
		}
		Color = *FoundColor;
	}

	float Thickness = 2.0f;
	if (const FString* ThicknessStr = Kw.Find(TEXT("thickness")))
	{
		Thickness = FCString::Atof(**ThicknessStr);
	}

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
	if (!World)
	{
		Writer->WriteValue(TEXT("status"), TEXT("No valid world found"));
		Writer->WriteObjectEnd();
		Writer->Close();
		return FExecStatus::OK(MoveTemp(Out));
	}

	for (int32 i = 0; i + 1 < Centers.Num(); ++i)
    {
        DrawDebugDirectionalArrow(
            World,
            Centers[i],
            Centers[i + 1],
			/*ArrowSize=*/30.0f,
            Color,
            /*bPersistentLines=*/true,
            /*LifeTime=*/-1.f,
            /*DepthPriority=*/0,
            /*Thickness=*/Thickness
        );
    }

	Writer->WriteValue(TEXT("status"), TEXT("ok"));
	Writer->WriteObjectEnd();
	Writer->Close();
	return FExecStatus::OK(MoveTemp(Out));
#else
	Writer->WriteValue(TEXT("status"), TEXT("Running DrawDebugLine from outside editor"));
	Writer->WriteObjectEnd();
	Writer->Close();
	return FExecStatus::OK(MoveTemp(Out));
#endif
}

FExecStatus FLychSimDataHandler::LSClearDebugLines(const TArray<FString>& Pos, const TMap<FString,FString>& Kw, const TSet<FString>& Flags)
{
	FString Out;
    TSharedRef< TJsonWriter<> > Writer = TJsonWriterFactory<>::Create(&Out);
	Writer->WriteObjectStart();

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

	if (!World)
	{
		Writer->WriteValue(TEXT("status"), TEXT("No valid world found"));
	}
	else
	{
		FlushPersistentDebugLines(World);
		Writer->WriteValue(TEXT("status"), TEXT("ok"));
	}

	Writer->WriteObjectEnd();
	Writer->Close();
	return FExecStatus::OK(MoveTemp(Out));
}

FExecStatus FLychSimDataHandler::LSPause(
	const TArray<FString>& Pos,
	const TMap<FString,FString>& Kw,
	const TSet<FString>& Flags)
{
	FString Out;
    TSharedRef< TJsonWriter<> > Writer = TJsonWriterFactory<>::Create(&Out);
	Writer->WriteObjectStart();

	UGameplayStatics::SetGamePaused(FUnrealcvServer::Get().GetWorld(), true);
	Writer->WriteValue(TEXT("status"), TEXT("ok"));

	return FExecStatus::OK(MoveTemp(Out));
}

FExecStatus FLychSimDataHandler::LSUnPause(
	const TArray<FString>& Pos,
	const TMap<FString,FString>& Kw,
	const TSet<FString>& Flags)
{
	FString Out;
    TSharedRef< TJsonWriter<> > Writer = TJsonWriterFactory<>::Create(&Out);
	Writer->WriteObjectStart();

	UGameplayStatics::SetGamePaused(FUnrealcvServer::Get().GetWorld(), false);
	Writer->WriteValue(TEXT("status"), TEXT("ok"));

	return FExecStatus::OK(MoveTemp(Out));
}
