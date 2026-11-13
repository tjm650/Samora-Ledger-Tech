"use client";
import {useEffect,useState, type ReactNode} from "react";
import {createPortal} from "react-dom";

export default function HeaderActions({children}:{children:ReactNode}){
 const [target,setTarget]=useState<HTMLElement|null>(null);
 useEffect(()=>{setTarget(document.getElementById("header-actions-slot"))},[]);
 return target?createPortal(<div className="header-actions">{children}</div>,target):null;
}
