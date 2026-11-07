from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.logging import bind_request_id, configure_logging, get_logger
from app.core.response import ApiError, error_response, success_response

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("app_startup")
    yield
    logger.info("app_shutdown")


app = FastAPI(
    title="Personal Assistant API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or __import__("uuid").uuid4().hex
    request.state.request_id = request_id
    bind_request_id(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return error_response(
        code=exc.code,
        message=exc.message,
        data=exc.data,
        status=exc.status,
        request_id=getattr(request.state, "request_id", ""),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return error_response(
        code="PARAM_INVALID",
        message="invalid request parameters",
        data={"errors": exc.errors()},
        status=400,
        request_id=getattr(request.state, "request_id", ""),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code = "INTERNAL_ERROR"
    if exc.status_code == 404:
        code = "RESOURCE_NOT_FOUND"
    elif exc.status_code == 403:
        code = "ACCESS_DENIED"
    elif exc.status_code == 401:
        code = "AUTH_INVALID"
    return error_response(
        code=code,
        message=exc.detail,
        status=exc.status_code,
        request_id=getattr(request.state, "request_id", ""),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_error", error=str(exc))
    return error_response(
        code="INTERNAL_ERROR",
        message="internal server error",
        status=500,
        request_id=getattr(request.state, "request_id", ""),
    )


@app.get("/")
async def root(request: Request):
    return success_response(
        data={"service": "personal-assistant", "version": "0.1.0"},
        request_id=request.state.request_id,
    )


app.include_router(api_router, prefix="/api/v1")
