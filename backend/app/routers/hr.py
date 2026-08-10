from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, database
from ..dependencies.permissions import require_roles
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy import func

router = APIRouter(
    prefix="/hr",
    tags=["hr"]
)

get_db = database.get_db

class EmployeeCreate(BaseModel):
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    role_function: Optional[str] = None
    salary: float = 0.0
    vacation_days_available: int = 14
    user_id: Optional[int] = None
    hire_date: Optional[datetime] = None

class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    role_function: Optional[str] = None
    salary: Optional[float] = None
    vacation_days_available: Optional[int] = None
    absent_days_this_month: Optional[int] = None
    hire_date: Optional[datetime] = None

@router.get("/employees")
def get_employees(db: Session = Depends(get_db), current_user: models.User = Depends(require_roles("admin"))):
    return db.query(models.Employee).all()

@router.post("/employees")
def create_employee(employee: EmployeeCreate, db: Session = Depends(get_db), current_user: models.User = Depends(require_roles("admin"))):
    email_val = employee.email.strip() if employee.email and employee.email.strip() else None
    phone_val = employee.phone.strip() if employee.phone and employee.phone.strip() else None
    address_val = employee.address.strip() if employee.address and employee.address.strip() else None

    if email_val:
        existing = db.query(models.Employee).filter(models.Employee.email == email_val).first()
        if existing:
            raise HTTPException(status_code=400, detail="Ya existe un empleado con este correo electrónico.")

    db_emp = models.Employee(
        first_name=employee.first_name,
        last_name=employee.last_name,
        email=email_val,
        phone=phone_val,
        address=address_val,
        role_function=employee.role_function,
        salary=employee.salary,
        vacation_days_available=employee.vacation_days_available,
        user_id=employee.user_id,
        hire_date=employee.hire_date if employee.hire_date else datetime.now()
    )
    db.add(db_emp)
    try:
        db.commit()
        db.refresh(db_emp)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error al guardar el empleado. Posible duplicado de datos únicos.")
    return db_emp

@router.put("/employees/{emp_id}")
def update_employee(emp_id: int, employee: EmployeeUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(require_roles("admin"))):
    db_emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not db_emp:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    update_dict = employee.model_dump(exclude_unset=True)

    # Normalize fields
    if "email" in update_dict:
        val = update_dict["email"].strip() if update_dict["email"] and update_dict["email"].strip() else None
        if val and val != db_emp.email:
            existing = db.query(models.Employee).filter(models.Employee.email == val).first()
            if existing:
                raise HTTPException(status_code=400, detail="Ya existe un empleado con este correo electrónico.")
        update_dict["email"] = val

    if "phone" in update_dict:
        update_dict["phone"] = update_dict["phone"].strip() if update_dict["phone"] and update_dict["phone"].strip() else None

    if "address" in update_dict:
        update_dict["address"] = update_dict["address"].strip() if update_dict["address"] and update_dict["address"].strip() else None

    for var, value in update_dict.items():
        setattr(db_emp, var, value)
            
    try:
        db.commit()
        db.refresh(db_emp)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error al actualizar el empleado. Posible duplicado.")
    return db_emp

@router.delete("/employees/{emp_id}")
def delete_employee(emp_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(require_roles("admin"))):
    db_emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not db_emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.delete(db_emp)
    db.commit()
    return {"status": "success"}

@router.post("/employees/{emp_id}/pay")
def pay_employee(emp_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(require_roles("admin"))):
    db_emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if not db_emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Get commissions if user_id is linked (dummy logic for now)
    commissions = 0.0
    if db_emp.user_id:
        # Example logic: calculate commissions from sales
        pass
        
    # Reset absent days for the new month
    db_emp.absent_days_this_month = 0
    db.commit()
    
    return {
        "status": "success",
        "message": f"Pago generado para {db_emp.first_name}.",
        "details": {
            "base_salary": float(db_emp.salary or 0),
            "commissions": commissions,
            "total_payout": float(db_emp.salary or 0) + commissions
        }
    }
